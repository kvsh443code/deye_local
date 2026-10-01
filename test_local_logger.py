import socket
import struct
import sys

from settings import setting

HOST = setting("LOCAL_BIND")
PORT = int(setting("LOCAL_PORT"))
LOGGER_SN = int(setting("LOGGER_SERIAL"))
START, COUNT = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (183, 10)


def crc(data):
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c


rtu = bytes([0x01, 0x03]) + struct.pack(">HH", START, COUNT)
rtu += struct.pack("<H", crc(rtu))
payload = b"\x02" + b"\x00\x00" + b"\x00" * 12 + rtu
frame = bytearray(b"\xa5" + struct.pack("<H", len(payload)) + b"\x10\x45" + b"\x2a\x00" + struct.pack("<I", LOGGER_SN) + payload + b"\x00\x15")
frame[-2] = sum(frame[1:-2]) & 0xFF

s = socket.create_connection((HOST, PORT), timeout=2 * float(setting("READ_TIMEOUT_S")))
s.sendall(frame)
resp = s.recv(4096)
s.close()

assert resp[0] == 0xA5 and resp[-1] == 0x15, "bad V5 framing"
assert resp[3:5] == b"\x10\x15", f"unexpected control code {resp[3:5].hex()}"
assert resp[5] == 0x2A, "sequence number not echoed"
assert sum(resp[1:-2]) & 0xFF == resp[-2], "bad V5 checksum"
rtu_resp = resp[11 + 14:-2]
assert crc(rtu_resp[:-2]) == struct.unpack("<H", rtu_resp[-2:])[0], "bad Modbus CRC"
n = rtu_resp[2] // 2
values = struct.unpack(f">{n}H", rtu_resp[3:3 + 2 * n])
print("OK", {START + i: v for i, v in enumerate(values)})
