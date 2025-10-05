import socket
import sys
import logging
import threading
import base64   # <-- for decoding payloads safely


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [RECEIVER] %(message)s",
                    datefmt="%H:%M:%S")

# Global stop flag
stop_flag = False

def user_input_listener():
    """Background thread to allow user to stop receiver with input."""
    global stop_flag
    while True:
        cmd = input()
        if cmd.lower() in ("q", "quit", "exit"):
            stop_flag = True
            logging.info("[INFO] Receiver stopped by user command.")
            break

def reliable_recv(sock):
    """Receive packet with timeout handling."""
    try:
        msg, addr = sock.recvfrom(2048)  # increased buffer to fit 512b + headers
        return msg.decode(errors="ignore"), addr
    except socket.timeout:
        return None, None

def gbn_recv(sock, outfile):
    global stop_flag
    expected_seq = 0
    with open(outfile, "wb") as f:  # binary mode
        while not stop_flag:
            msg, addr = reliable_recv(sock)
            if msg is None:
                continue

            if msg == "END":
                logging.info("[INFO] Transmission complete (GBN)")
                break

            parts = msg.split("-", 2)  # split only twice
            if len(parts) < 3:
                continue
            seq, payload_b64 = int(parts[1]), parts[2]

            if seq == expected_seq:
                # decode once, write once
                try:
                    chunk = base64.b64decode(payload_b64)
                except Exception as e:
                    logging.error(f"[ERROR] Base64 decode failed: {e}")
                    continue

                logging.info(f"[RECV] seq={seq}, decoded_bytes={len(chunk)}")
                f.write(chunk)

                ack = f"ACK-{seq}"
                sock.sendto(ack.encode(), addr)
                logging.info(f"[SEND] {ack}")
                expected_seq += 1
            else:
                # GBN: only ack last in-order packet
                ack_num = max(expected_seq - 1, 0)
                ack = f"ACK-{ack_num}"
                sock.sendto(ack.encode(), addr)
                logging.info(f"[SEND] {ack} (dup)")
    logging.info("[INFO] GBN receiver loop ended.")

def sr_recv(sock, window_size, outfile):
    global stop_flag
    expected_seq = 0
    buffer = {}
    with open(outfile, "wb") as f:  # binary mode
        while not stop_flag:
            msg, addr = reliable_recv(sock)
            if msg is None:
                continue

            if msg == "END":
                logging.info("[INFO] Transmission complete (SR)")
                break

            parts = msg.split("-", 2)  
            if len(parts) < 3:
                continue
            seq, payload_b64 = int(parts[1]), parts[2]

            if expected_seq <= seq < expected_seq + window_size:
                
                try:
                    decoded = base64.b64decode(payload_b64)
                except Exception as e:
                    logging.error(f"[ERROR] Base64 decode failed: {e}")
                    continue

                logging.info(f"[RECV] seq={seq}, decoded_bytes={len(decoded)}")
                buffer[seq] = decoded

                ack = f"ACK-{seq}"
                sock.sendto(ack.encode(), addr)
                logging.info(f"[SEND] {ack}")

                
                while expected_seq in buffer:
                    f.write(buffer[expected_seq])
                    del buffer[expected_seq]
                    expected_seq += 1
            else:
                
                ack = f"ACK-{seq}"
                sock.sendto(ack.encode(), addr)
                logging.info(f"[SEND] {ack} (out of window)")
    logging.info("[INFO] SR receiver loop ended.")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python receiver.py <port> <mode: gbn/sr> <outfile>")
        sys.exit(1)

    port = int(sys.argv[1])
    mode = sys.argv[2].lower()
    outfile = sys.argv[3]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", port))
    sock.settimeout(1.0)  

    logging.info(f"[INFO] Receiver listening on 127.0.0.1:{port} ({mode.upper()})")

    # Start user input thread
    threading.Thread(target=user_input_listener, daemon=True).start()

    if mode == "gbn":
        gbn_recv(sock, outfile)
    elif mode == "sr":
        window_size = 5  # default
        sr_recv(sock, window_size, outfile)
    else:
        print("Invalid mode! Use 'gbn' or 'sr'.")

    sock.close()
