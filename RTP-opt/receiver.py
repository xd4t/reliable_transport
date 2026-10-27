"""RTP receiver (optimized version): buffers out-of-order packets and ACKs
each packet individually with its own seq_num (no cumulative ACK)."""

import argparse
import socket
import sys

from utils import PacketHeader, compute_checksum

# Packet types
START, END, DATA, ACK = 0, 1, 2, 3

HEADER_LEN = 16


def parse_packet(raw):
    """Return (header, payload) if the packet is well-formed and its checksum
    matches, otherwise None (the packet must then be dropped silently)."""
    if len(raw) < HEADER_LEN:
        return None
    header = PacketHeader(raw[:HEADER_LEN])
    payload = raw[HEADER_LEN:HEADER_LEN + header.length]
    if len(payload) != header.length:
        return None
    received = header.checksum
    header.checksum = 0
    if compute_checksum(header / payload) != received:
        return None
    return header, payload


def send_ack(sock, seq, addr):
    header = PacketHeader(type=ACK, seq_num=seq, length=0, checksum=0)
    header.checksum = compute_checksum(header)
    sock.sendto(bytes(header), addr)


def receiver(receiver_ip, receiver_port, window_size):
    """Listen on socket and print received message to sys.stdout."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((receiver_ip, receiver_port))
    out = sys.stdout.buffer

    connected = False
    expected = 0    # next in-order seq_num (N)
    buffer = {}     # seq_num -> payload, for packets inside the window

    while True:
        raw, addr = sock.recvfrom(2048)
        parsed = parse_packet(raw)
        if parsed is None:
            continue  # corrupted: drop without ACK
        header, payload = parsed
        ptype, seq = header.type, header.seq_num

        if not connected:
            # Only a START packet can open a connection
            if ptype == START and seq == 0:
                connected = True
                expected = 1
                send_ack(sock, expected, addr)
            continue

        if ptype == START:
            # START in the middle of a connection is ignored
            continue

        if ptype == DATA:
            if seq >= expected + window_size:
                continue  # beyond the window: drop, no ACK
            if seq >= expected:
                buffer.setdefault(seq, payload)
                # Deliver every in-order packet we now have
                while expected in buffer:
                    out.write(buffer.pop(expected))
                    expected += 1
                out.flush()
            # ACK exactly this packet's seq_num (also for duplicates below
            # the window, so a lost ACK can be repaired)
            send_ack(sock, seq, addr)

        elif ptype == END and seq == expected:
            # All data has been delivered; ACK the END and finish
            send_ack(sock, seq, addr)
            break

    out.flush()
    sock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "receiver_ip", help="The IP address of the host that receiver is running on"
    )
    parser.add_argument(
        "receiver_port", type=int, help="The port number on which receiver is listening"
    )
    parser.add_argument(
        "window_size", type=int, help="Maximum number of outstanding packets"
    )
    args = parser.parse_args()

    receiver(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
