"""Log sway window events as "change con_id" lines to FILE (for counting focus events)."""
import json
import os
import socket
import struct
import sys

HEADER = struct.Struct("=6sII")


def recv_exact(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise SystemExit(0)
        buf += chunk
    return buf


def main():
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(os.environ["SWAYSOCK"])
    payload = b'["window"]'
    s.sendall(HEADER.pack(b"i3-ipc", len(payload), 2) + payload)
    with open(sys.argv[1], "a", buffering=1) as out:
        while True:
            _, length, kind = HEADER.unpack(recv_exact(s, HEADER.size))
            body = json.loads(recv_exact(s, length))
            if kind == 0x80000003:
                out.write(f'{body["change"]} {body["container"]["id"]}\n')


if __name__ == "__main__":
    main()
