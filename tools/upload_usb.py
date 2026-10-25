#!/usr/bin/env python3
"""macOS/Linux USB CLI storage uploader; never starts Bad KB or types keys."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import select
import sys
import termios
import time
import tty
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flippykb.__main__ import remote_path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('script', type=Path)
    p.add_argument('--device', required=True, help='Flipper USB serial device, not ESP32 board')
    p.add_argument('--remote', required=True)
    args = p.parse_args()
    remote = remote_path(args.remote)
    if not re.fullmatch(r'/ext/badusb/[A-Za-z0-9_.-]+\.txt', remote):
        p.error('USB CLI upload requires a simple filename under /ext/badusb/')
    data = args.script.read_bytes()
    if not data:
        p.error('empty script')
    fd = os.open(args.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    previous = termios.tcgetattr(fd)

    def read_until(marker=b'>: ', timeout=60):
        out = b''
        deadline = time.monotonic() + timeout
        while marker not in out:
            if time.monotonic() > deadline:
                raise TimeoutError('serial response timeout')
            if select.select([fd], [], [], .1)[0]:
                out += os.read(fd, 65536)
        return out

    def send(buf):
        while buf:
            if not select.select([], [fd], [], 2)[1]:
                raise TimeoutError('serial write timeout')
            n = os.write(fd, buf)
            buf = buf[n:]

    def command(text):
        send(text.encode() + b'\r')
        return read_until()

    try:
        tty.setraw(fd)
        send(b'\r')
        while select.select([fd], [], [], .5)[0]:
            os.read(fd, 65536)
        if b'not exist' not in command('storage stat ' + remote).lower():
            raise RuntimeError('destination exists or stat failed; choose a new filename')
        for offset in range(0, len(data), 512):
            chunk = data[offset:offset+512]
            send(f'storage write_chunk {remote} {len(chunk)}\r'.encode())
            if b'error' in read_until(b'Ready\r\n').lower():
                raise RuntimeError('write refused')
            send(chunk)
            if b'error' in read_until().lower():
                raise RuntimeError('write failed')
        result = command('storage read ' + remote)
        match = re.search(rb'Size: (\d+)\r\n', result)
        if not match or int(match[1]) != len(data) or result[match.end():match.end()+len(data)] != data:
            raise RuntimeError('readback mismatch')
        print('Exact USB upload readback verified:', remote)
        print('SHA-256:', hashlib.sha256(data).hexdigest())
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, previous)
        os.close(fd)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, TimeoutError):
        sys.exit('USB upload failed; no script started. Check device and choose a new destination before retrying.')
