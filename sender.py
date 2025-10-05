import socket
import sys
import time
import random
import logging
import base64  


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [SENDER] %(message)s",
                    datefmt="%H:%M:%S")

def unreliable_send(sock, message, addr, loss_rate):
    """Simulate random packet loss before sending."""
    if random.random() < loss_rate:
        logging.warning(f"[LOSS] Dropped packet: {message[:50]}...")  # trim for log
        return
    sock.sendto(message.encode(), addr)


def gbn_send(sock, addr, data, window_size, loss_rate, timeout):
    base, next_seq = 0, 0
    total_packets = len(data)
    packet_buffer = [f"DATA-{i}-{data[i]}" for i in range(total_packets)]

    while base < total_packets:
        # Send new packets 
        while next_seq < base + window_size and next_seq < total_packets:
            unreliable_send(sock, packet_buffer[next_seq], addr, loss_rate)
            logging.info(f"[SEND] seq={next_seq}")
            next_seq += 1

        sock.settimeout(timeout)
        try:
            ack_msg, _ = sock.recvfrom(1024)
            ack_seq = int(ack_msg.decode().split("-")[1])
            logging.info(f"[ACK] {ack_seq}")
            if ack_seq >= base:
                base = ack_seq + 1
        except socket.timeout:
            logging.warning("[TIMEOUT] Resending window")
            for i in range(base, next_seq):
                unreliable_send(sock, packet_buffer[i], addr, loss_rate)
                logging.info(f"[RETX] seq={i}")

    #  End transfer
    time.sleep(0.5)
    unreliable_send(sock, "END", addr, 0)
    logging.info("[INFO] Transmission complete (GBN)")


def sr_send(sock, addr, data, window_size, loss_rate, timeout):
    base, next_seq = 0, 0
    total_packets = len(data)
    packet_buffer = [f"DATA-{i}-{data[i]}" for i in range(total_packets)]
    acked = [False] * total_packets
    timers = {}

    while base < total_packets:
        # Send new packats
        while next_seq < base + window_size and next_seq < total_packets:
            unreliable_send(sock, packet_buffer[next_seq], addr, loss_rate)
            timers[next_seq] = time.time()
            logging.info(f"[SEND] seq={next_seq}")
            next_seq += 1

        sock.settimeout(timeout)
        try:
            ack_msg, _ = sock.recvfrom(1024)
            ack_seq = int(ack_msg.decode().split("-")[1])
            if not acked[ack_seq]:
                acked[ack_seq] = True
                logging.info(f"[ACK] {ack_seq}")
                while base < total_packets and acked[base]:
                    base += 1
        except socket.timeout:
            pass

        # Retransmit 
        for seq in range(base, next_seq):
            if not acked[seq] and time.time() - timers[seq] > timeout:
                unreliable_send(sock, packet_buffer[seq], addr, loss_rate)
                timers[seq] = time.time()
                logging.warning(f"[RETX] seq={seq}")

    # End  transfer
    time.sleep(0.5)
    unreliable_send(sock, "END", addr, 0)
    logging.info("[INFO] Transmission complete (SR)")


if __name__ == "__main__":
    if len(sys.argv) < 8:
        print("Usage: python sender.py <receiver_ip> <receiver_port> <mode: gbn/sr> <window_size> <loss_rate> <timeout> <filename>")
        sys.exit(1)

    receiver_ip = sys.argv[1]
    receiver_port = int(sys.argv[2])
    mode = sys.argv[3].lower()
    window_size = int(sys.argv[4])
    loss_rate = float(sys.argv[5])
    timeout = float(sys.argv[6])  # timeout
    filename = sys.argv[7]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = (receiver_ip, receiver_port)

    #  Load file in binary & split into 512B chunks
    PACKET_SIZE = 512
    file_data = []
    with open(filename, "rb") as f:
        while True:
            chunk = f.read(PACKET_SIZE)
            if not chunk:
                break
            encoded = base64.b64encode(chunk).decode()
            file_data.append(encoded)

    if mode == "gbn":
        gbn_send(sock, addr, file_data, window_size, loss_rate, timeout)
    elif mode == "sr":
        sr_send(sock, addr, file_data, window_size, loss_rate, timeout)
    else:
        print("Invalid mode! Use 'gbn' or 'sr'.")

    sock.close()
