import os
import subprocess

def main():
    # Ask user for inputs
    mode = input("Enter mode (gbn/sr): ").strip().lower()
    window_size = input("Enter window size: ").strip()
    packet_loss = input("Enter packet loss %: ").strip()
    delay = input("Enter delay : ").strip()

    # Path where sender.py and receiver.py are located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Receiver command
    receiver_cmd = f'python receiver.py 5000 {mode} rec.txt'
    # Sender command
    sender_cmd = f'python sender.py 127.0.0.1 5000 {mode} {window_size} {packet_loss} {delay} input.txt'

    # Open receiver in a new cmd window
    subprocess.Popen(
        f'start cmd /K "cd /d {script_dir} && {receiver_cmd}"',
        shell=True
    )

    # Open sender in a new cmd window
    subprocess.Popen(
        f'start cmd /K "cd /d {script_dir} && {sender_cmd}"',
        shell=True
    )

if __name__ == "__main__":
    main()
