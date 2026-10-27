"""RTP sender (optimized version): sliding window + per-packet ACK.
Only packets that have not been ACKed are retransmitted on timeout."""

import argparse
import select
import socket
import sys
import time

from utils import PacketHeader, compute_checksum

# Packet types
START, END, DATA, ACK = 0, 1, 2, 3

HEADER_LEN = 16
MAX_PACKET = 1472                     # 1500 (Ethernet) - 20 (IP) - 8 (UDP)
CHUNK_SIZE = MAX_PACKET - HEADER_LEN  # payload bytes per DATA packet
TIMEOUT = 0.5                         # retransmission timer, seconds


def build_packet(ptype, seq, payload=b""):
    """Create the raw bytes of an RTP packet with a CRC32 checksum."""
    header = PacketHeader(type=ptype, seq_num=seq, length=len(payload), checksum=0)
    header.checksum = compute_checksum(header / payload)
    return bytes(header / payload)


def parse_ack(raw):
    """Return the seq_num of a valid ACK packet, or None if it is invalid/corrupt."""
    if len(raw) < HEADER_LEN:
        return None
    header = PacketHeader(raw[:HEADER_LEN])
    if header.type != ACK or header.length != 0:
        return None
    received = header.checksum
    header.checksum = 0
    if compute_checksum(header) != received:
        return None
    return header.seq_num


def wait_for_ack(sock, deadline):
    """Block until an ACK arrives or the deadline passes. Returns seq or None."""
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return None
        ready, _, _ = select.select([sock], [], [], remaining)
        if not ready:
            return None
        raw, _ = sock.recvfrom(2048)
        seq = parse_ack(raw)
        if seq is not None:
            return seq


def sender(receiver_ip, receiver_port, window_size):
    """Open socket and send message from sys.stdin."""
    dest = (receiver_ip, receiver_port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    message = sys.stdin.buffer.read()
    chunks = [message[i:i + CHUNK_SIZE] for i in range(0, len(message), CHUNK_SIZE)]
    # DATA packets use seq_num 1..len(chunks); packets[k] has seq_num k + 1
    packets = [build_packet(DATA, k + 1, chunk) for k, chunk in enumerate(chunks)]
    last_seq = len(packets)

    # --- 1. Connection setup: START (seq 0) and wait for ACK with seq 1 ---
    start_pkt = build_packet(START, 0)
    while True:
        sock.sendto(start_pkt, dest)
        if wait_for_ack(sock, time.time() + TIMEOUT) == 1:
            break

    # --- 2. Data transfer: selective ACK, one timer for the whole window ---
    base = 1          # oldest seq_num not yet acknowledged
    next_seq = 1      # next seq_num that has never been sent
    acked = set()     # seq_nums in the window that the receiver has ACKed
    timer = time.time() + TIMEOUT

    while base <= last_seq:
        # Fill the window with packets that have not been sent yet
        while next_seq < base + window_size and next_seq <= last_seq:
            sock.sendto(packets[next_seq - 1], dest)
            next_seq += 1

        ack = wait_for_ack(sock, timer)
        if ack is None:
            # Timer expired: resend only the packets in the window not yet ACKed
            for seq in range(base, next_seq):
                if seq not in acked:
                    sock.sendto(packets[seq - 1], dest)
            timer = time.time() + TIMEOUT
        elif base <= ack < next_seq:
            # Individual ACK: mark that one packet as received
            acked.add(ack)
            if ack == base:
                # Slide the window past every consecutive ACKed packet
                while base in acked:
                    acked.discard(base)
                    base += 1
                timer = time.time() + TIMEOUT
        # Any other ACK is stale or duplicate: ignore

    # --- 3. Teardown: send END and wait at most 500 ms for its ACK ---
    end_seq = last_seq + 1
    sock.sendto(build_packet(END, end_seq), dest)
    deadline = time.time() + TIMEOUT
    while True:
        ack = wait_for_ack(sock, deadline)
        if ack is None or ack == end_seq:
            break

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

    sender(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
