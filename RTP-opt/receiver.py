import argparse
import socket
import sys

from utils import PacketHeader, compute_checksum

START, END, DATA, ACK = 0, 1, 2, 3


def send_ack(s, seq, addr):
    h = PacketHeader(type=ACK, seq_num=seq, length=0)
    h.checksum = compute_checksum(h)
    s.sendto(bytes(h), addr)


def receiver(receiver_ip, receiver_port, window_size):
    """Listen on socket and print received message to sys.stdout."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))

    started = False
    expected = 0
    buf = {}

    while True:
        pkt, addr = s.recvfrom(2048)
        if len(pkt) < 16:
            continue
        h = PacketHeader(pkt[:16])
        data = pkt[16:16 + h.length]
        c = h.checksum
        h.checksum = 0
        if len(data) != h.length or compute_checksum(h / data) != c:
            continue

        if not started:
            if h.type == START:
                started = True
                expected = 1
                send_ack(s, 1, addr)
            continue

        if h.type == DATA:
            seq = h.seq_num
            if seq >= expected + window_size:
                continue
            if seq >= expected:
                buf[seq] = data
                while expected in buf:
                    sys.stdout.buffer.write(buf.pop(expected))
                    expected += 1
                sys.stdout.flush()
            # ack dung seq cua goi (khong cong don)
            send_ack(s, seq, addr)
        elif h.type == END and h.seq_num == expected:
            send_ack(s, expected, addr)
            break

    sys.stdout.flush()
    s.close()


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
