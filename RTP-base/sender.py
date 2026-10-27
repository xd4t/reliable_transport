import argparse
import socket
import sys
import time

from utils import PacketHeader, compute_checksum

START, END, DATA, ACK = 0, 1, 2, 3
CHUNK = 1472 - 16
TIMEOUT = 0.5


def make_packet(t, seq, data=b""):
    h = PacketHeader(type=t, seq_num=seq, length=len(data))
    h.checksum = compute_checksum(h / data)
    return bytes(h / data)


def get_ack(s, until):
    # tra ve seq cua ACK, hoac None neu het gio
    while time.time() < until:
        s.settimeout(until - time.time())
        try:
            pkt, _ = s.recvfrom(2048)
        except socket.timeout:
            return None
        if len(pkt) < 16:
            continue
        h = PacketHeader(pkt[:16])
        c = h.checksum
        h.checksum = 0
        if h.type == ACK and compute_checksum(h) == c:
            return h.seq_num
    return None


def sender(receiver_ip, receiver_port, window_size):
    """Open socket and send message from sys.stdin."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = (receiver_ip, receiver_port)

    msg = sys.stdin.buffer.read()
    pkts = []
    for i in range(0, len(msg), CHUNK):
        pkts.append(make_packet(DATA, len(pkts) + 1, msg[i:i + CHUNK]))
    n = len(pkts)

    while True:
        s.sendto(make_packet(START, 0), addr)
        if get_ack(s, time.time() + TIMEOUT) == 1:
            break

    base = 1
    nxt = 1
    timer = time.time() + TIMEOUT
    while base <= n:
        while nxt < base + window_size and nxt <= n:
            s.sendto(pkts[nxt - 1], addr)
            nxt += 1

        ack = get_ack(s, timer)
        if ack is None:
            # timeout -> gui lai ca cua so
            for i in range(base, nxt):
                s.sendto(pkts[i - 1], addr)
            timer = time.time() + TIMEOUT
        elif ack > base:
            base = min(ack, n + 1)
            timer = time.time() + TIMEOUT

    s.sendto(make_packet(END, n + 1), addr)
    end_time = time.time() + TIMEOUT
    while True:
        ack = get_ack(s, end_time)
        if ack is None or ack == n + 2:
            break
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

    sender(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
