import datetime
import json
import socket
import ssl
import struct
import sys
import threading
import time

from register_map import describe
from settings import setting

LISTEN = (setting("HOTSPOT_GATEWAY"), int(setting("PROXY_PORT")))
UPSTREAM = (setting("UPSTREAM_HOST"), int(setting("UPSTREAM_PORT")))
CONF_DIR = setting("CONF_DIR")
LOG_DIR = setting("LOG_DIR")

LOCAL_LOGGER = (setting("LOCAL_BIND"), int(setting("LOCAL_PORT")))
LOCAL_ALLOWED = {a.strip() for a in setting("LOCAL_ALLOW").split(",") if a.strip()}
READ_FUNCTIONS = (0x03, 0x04)

POLL_MODE = sys.argv[1] if len(sys.argv) > 1 else setting("POLL_MODE")
DISCOVER_RANGE = range(int(setting("DISCOVER_FIRST_REG")), int(setting("DISCOVER_LAST_REG")) + 1)
POLL_REGS = list(range(int(setting("POLL_FIRST_REG")), int(setting("POLL_LAST_REG")) + 1))
POLL_INTERVAL_S = float(setting("POLL_INTERVAL_S"))
POLL_BATCH_GAP_S = float(setting("POLL_BATCH_GAP_S"))
BATCH = int(setting("READ_BATCH_SIZE"))
SPACING_S = float(setting("DISCOVER_BATCH_GAP_S"))
REPLY_TIMEOUT_S = float(setting("READ_TIMEOUT_S"))
START_DELAY_S = float(setting("READ_START_DELAY_S"))
PROBE_REG = int(setting("PROBE_FIRST_REG"))
PROBE_COUNT = int(setting("PROBE_REG_COUNT"))

STICK_IDLE_TIMEOUT_S = float(setting("STICK_IDLE_TIMEOUT_S"))
CLOUD_CONNECT_TIMEOUT_S = float(setting("CLOUD_CONNECT_TIMEOUT_S"))
CLOUD_IDLE_TIMEOUT_S = float(setting("CLOUD_IDLE_TIMEOUT_S"))
LOCAL_IDLE_TIMEOUT_S = float(setting("LOCAL_IDLE_TIMEOUT_S"))

READ_HOLDING = 0x03

LOG = open(f"{LOG_DIR}/deye-proxy.log", "a", buffering=1)
FRAMES = open(f"{LOG_DIR}/deye-proxy-frames.hex", "a", buffering=1)
REGS = open(f"{LOG_DIR}/deye-registers.jsonl", "a", buffering=1)
LIVE = open(f"{LOG_DIR}/deye-live.jsonl", "a", buffering=1)
CLOUD_READS = open(f"{LOG_DIR}/deye-cloud-reads.log", "a", buffering=1)

CURRENT = {"session": None}
TYPES = {0x41: "HANDSHAKE", 0x42: "DATA", 0x43: "WIFI", 0x47: "HEARTBEAT", 0x48: "TYPE48", 0x4D: "TYPE4D",
         0x11: "HANDSHAKE_ACK", 0x12: "DATA_ACK", 0x13: "WIFI_ACK", 0x17: "HEARTBEAT_ACK", 0x18: "TYPE48_ACK",
         0x1D: "TYPE4D_ACK", 0x45: "CMD_TO_INVERTER", 0x15: "CMD_REPLY"}


def ts():
    return datetime.datetime.now().isoformat(timespec="seconds")


def log(m):
    LOG.write(f"{ts()} {m}\n")


server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
server_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
server_ctx.set_ciphers("ALL:@SECLEVEL=0")
server_ctx.load_cert_chain(f"{CONF_DIR}/mitm-cert.pem", f"{CONF_DIR}/mitm-key.pem")

client_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
client_ctx.load_verify_locations(f"{CONF_DIR}/igen-ca.pem")
client_ctx.check_hostname = False
client_ctx.verify_mode = ssl.CERT_REQUIRED


def checksum(frame):
    return sum(frame[1:-2]) & 0xFF


def parse_batch_request(payload):
    if len(payload) < 17 or payload[0] not in (0x04, 0x05):
        return None
    writes = payload[0] == 0x05
    entries, off = [], 17
    for _ in range(payload[16]):
        if off + 4 > len(payload):
            break
        fc, reg, count = payload[off], struct.unpack(">H", payload[off + 1:off + 3])[0], payload[off + 3]
        off += 4
        values = []
        if writes:
            values = [struct.unpack(">H", payload[off + 2 * k:off + 2 * k + 2])[0] for k in range(count)]
            off += 2 * count
        entries.append((fc, reg, count, values))
    return "write" if writes else "read", entries


def parse_write_reply(payload, entries):
    statuses = payload[16:16 + len(entries)]
    return [(reg, status) for (_, reg, _, _), status in zip(entries, statuses)]


def parse_batch_reply(payload, entries):
    values, i = [], 16
    for fc, reg, count, _ in entries:
        if i >= len(payload):
            break
        n = payload[i]
        data = payload[i + 1:i + 1 + n]
        i += 1 + n
        for k in range(len(data) // 2):
            values.append((reg + k, struct.unpack(">H", data[2 * k:2 * k + 2])[0]))
    return values


def modbus_crc(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class Splitter:
    def __init__(self):
        self.buf = b""

    def feed(self, data):
        self.buf += data
        out = []
        while self.buf:
            if self.buf[0] != 0xA5:
                idx = self.buf.find(b"\xa5")
                junk, self.buf = (self.buf, b"") if idx < 0 else (self.buf[:idx], self.buf[idx:])
                out.append(("raw", junk))
                continue
            if len(self.buf) < 3:
                break
            flen = 11 + struct.unpack_from("<H", self.buf, 1)[0] + 2
            if len(self.buf) < flen:
                break
            frame, self.buf = self.buf[:flen], self.buf[flen:]
            out.append(("frame", frame))
        return out


class Session:
    def __init__(self, stick, cloud):
        self.stick = stick
        self.cloud = cloud
        self.to_stick_lock = threading.Lock()
        self.done = threading.Event()
        self.serial = None
        self.recent_cloud_ids = []
        self.pending_id = None
        self.pending_regs = None
        self.reply = None
        self.reply_event = threading.Event()
        self.req_lock = threading.Lock()
        self.cloud_requests = {}

    def note_cloud_request(self, frame):
        try:
            payload = frame[11:-2]
            parsed = parse_batch_request(payload)
            if parsed is None:
                CLOUD_READS.write(f"{ts()} REQUEST unknown format {payload.hex(' ')}\n")
                return
            kind, entries = parsed
            stamp = ts()
            if kind == "write":
                for fc, reg, _, values in entries:
                    for k, value in enumerate(values):
                        CLOUD_READS.write(f"{stamp} WRITE fc=0x{fc:02x} {describe(reg + k, value)}\n")
            elif any(fc not in READ_FUNCTIONS for fc, _, _, _ in entries):
                CLOUD_READS.write(f"{stamp} REQUEST non read {payload.hex(' ')}\n")
            self.cloud_requests[frame[5]] = (kind, entries)
        except Exception as e:
            log(f"cloud request decode error: {e!r}")

    def note_cloud_reply(self, frame):
        try:
            request = self.cloud_requests.pop(frame[5], None)
            if request is None:
                return
            kind, entries = request
            stamp = ts()
            if kind == "write":
                for reg, status in parse_write_reply(frame[11:-2], entries):
                    result = "OK" if status == 0x01 else f"FAILED status=0x{status:02x}"
                    CLOUD_READS.write(f"{stamp} WRITE {result} {reg}\n")
                return
            for reg, raw in parse_batch_reply(frame[11:-2], entries):
                CLOUD_READS.write(f"{stamp} {describe(reg, raw)}\n")
        except Exception as e:
            log(f"cloud reply decode error: {e!r}")

    def record(self, direction, frame):
        name = TYPES.get(frame[4], f"0x{frame[4]:02x}")
        log(f"{direction} {name} len={len(frame)} id={frame[5]:02x}/{frame[6]:02x}")
        FRAMES.write(f"{ts()} {direction} {name} {frame.hex()}\n")

    def cloud_to_stick(self):
        sp = Splitter()
        try:
            while True:
                data = self.cloud.recv(8192)
                if not data:
                    break
                for kind, chunk in sp.feed(data):
                    if kind == "frame":
                        if chunk[4] == 0x45:
                            self.recent_cloud_ids = (self.recent_cloud_ids + [chunk[5]])[-20:]
                            self.note_cloud_request(chunk)
                        self.record("DOWN", chunk)
                    with self.to_stick_lock:
                        self.stick.sendall(chunk)
        except Exception as e:
            log(f"cloud->stick ended: {e!r}")
        finally:
            self.done.set()

    def stick_to_cloud(self):
        sp = Splitter()
        try:
            while True:
                data = self.stick.recv(8192)
                if not data:
                    break
                for kind, chunk in sp.feed(data):
                    if kind == "frame":
                        if self.serial is None:
                            self.serial = chunk[7:11]
                        if chunk[4] == 0x15 and self.pending_id is not None and chunk[5] == self.pending_id:
                            self.reply = chunk
                            self.reply_event.set()
                            FRAMES.write(f"{ts()} LOCAL CMD_REPLY {chunk.hex()}\n")
                            continue
                        if chunk[4] == 0x15:
                            self.note_cloud_reply(chunk)
                        self.record("UP  ", chunk)
                    self.cloud.sendall(chunk)
        except Exception as e:
            log(f"stick->cloud ended: {e!r}")
        finally:
            self.done.set()

    def pick_id(self):
        base = (self.recent_cloud_ids[-1] if self.recent_cloud_ids else 0x45) + 0x80
        for k in range(256):
            cand = (base + k) & 0xFF
            if all(abs(((cand - c + 128) & 0xFF) - 128) > 16 for c in self.recent_cloud_ids):
                return cand
        return base & 0xFF

    def build_read(self, msg_id, regs):
        entries = b"".join(bytes([READ_HOLDING]) + struct.pack(">H", r) + b"\x01" for r in regs)
        payload = b"\x04\x34\x54" + b"\x00" * 8 + struct.pack("<I", int(time.time())) + b"\x01" + bytes([len(regs)]) + entries
        frame = bytearray(b"\xa5" + struct.pack("<H", len(payload)) + bytes([0x10, 0x45, msg_id, 0x01]) + self.serial + payload + b"\x00\x15")
        frame[-2] = checksum(frame)
        assert all(frame[11 + 17 + 4 * i] == READ_HOLDING for i in range(len(regs)))
        return bytes(frame)

    def build_frame(self, msg_id, payload):
        frame = bytearray(b"\xa5" + struct.pack("<H", len(payload)) + bytes([0x10, 0x45, msg_id, 0x01]) + self.serial + payload + b"\x00\x15")
        frame[-2] = checksum(frame)
        return bytes(frame)

    def request(self, build):
        with self.req_lock:
            if self.done.is_set():
                return None
            msg_id = self.pick_id()
            self.reply = None
            self.reply_event.clear()
            self.pending_id = msg_id
            with self.to_stick_lock:
                self.stick.sendall(build(msg_id))
            got = self.reply_event.wait(REPLY_TIMEOUT_S)
            self.pending_id = None
            return self.reply if got else None

    def read(self, regs):
        reply = self.request(lambda msg_id: self.build_read(msg_id, regs))
        if reply is None:
            return None
        p = reply[11:-2]
        values, i = {}, 16
        for r in regs:
            if i >= len(p):
                break
            n = p[i]
            raw = p[i + 1:i + 1 + n]
            values[r] = int.from_bytes(raw, "big") if n == 2 else raw.hex()
            i += 1 + n
        return values

    def poller(self):
        if POLL_MODE not in ("discover", "poll", "probe"):
            return
        if self.done.wait(START_DELAY_S) or self.serial is None:
            return
        if POLL_MODE == "poll":
            self.poll_loop()
            return
        if POLL_MODE == "probe":
            self.probe()
            return
        regs = list(DISCOVER_RANGE)
        log(f"DISCOVER start: registers {regs[0]}..{regs[-1]} in batches of {BATCH}")
        found = 0
        for i in range(0, len(regs), BATCH):
            if self.done.is_set():
                break
            chunk = regs[i:i + BATCH]
            vals = self.read(chunk)
            if vals is None:
                log(f"DISCOVER no reply for {chunk[0]}..{chunk[-1]}")
            else:
                found += 1
                REGS.write(json.dumps({"t": ts(), "values": vals}) + "\n")
            self.done.wait(SPACING_S)
        log(f"DISCOVER done: {found} batches answered")

    def probe(self):
        def p1(msg_id):
            payload = b"\x04\x34\x54" + b"\x00" * 8 + struct.pack("<I", int(time.time())) + b"\x01\x01" + bytes([READ_HOLDING]) + struct.pack(">H", PROBE_REG) + bytes([PROBE_COUNT])
            return self.build_frame(msg_id, payload)

        def p2(msg_id):
            rtu = bytes([0x01, READ_HOLDING]) + struct.pack(">HH", PROBE_REG, PROBE_COUNT)
            rtu += struct.pack("<H", modbus_crc(rtu))
            payload = b"\x02" + b"\x00\x00" + b"\x00" * 12 + rtu
            return self.build_frame(msg_id, payload)

        for name, build in (("P1 batch count=10", p1), ("P2 raw modbus frametype=02", p2)):
            sent = build(0)
            reply = self.request(build)
            log(f"PROBE {name}: sent={sent[11:-2].hex(' ')} reply={'NONE' if reply is None else reply.hex(' ')}")
            self.done.wait(SPACING_S)
        log("PROBE done")

    def poll_loop(self):
        log(f"POLL start: {len(POLL_REGS)} registers every {POLL_INTERVAL_S:.0f}s")
        misses = 0
        while not self.done.is_set():
            started = time.monotonic()
            snapshot = {}
            for i in range(0, len(POLL_REGS), BATCH):
                if self.done.is_set():
                    return
                vals = self.read(POLL_REGS[i:i + BATCH])
                if vals is None:
                    misses += 1
                    log(f"POLL no reply for {POLL_REGS[i]}..{POLL_REGS[min(i + BATCH, len(POLL_REGS)) - 1]} (misses={misses})")
                else:
                    snapshot.update(vals)
                self.done.wait(POLL_BATCH_GAP_S)
            if snapshot:
                LIVE.write(json.dumps({"t": ts(), "values": snapshot}) + "\n")
            self.done.wait(max(POLL_BATCH_GAP_S, POLL_INTERVAL_S - (time.monotonic() - started)))


def handle(raw, addr):
    log(f"STICK CONNECT {addr}")
    raw.settimeout(STICK_IDLE_TIMEOUT_S)
    try:
        stick = server_ctx.wrap_socket(raw, server_side=True)
    except Exception as e:
        log(f"stick TLS failed {addr}: {e!r}")
        raw.close()
        return
    try:
        up_raw = socket.create_connection(UPSTREAM, timeout=CLOUD_CONNECT_TIMEOUT_S)
        up_raw.settimeout(CLOUD_IDLE_TIMEOUT_S)
        cloud = client_ctx.wrap_socket(up_raw)
        log(f"CLOUD CONNECTED {cloud.getpeername()} {cloud.version()} (IGEN CA verified)")
    except Exception as e:
        log(f"cloud connect FAILED, dropping stick so it retries: {e!r}")
        stick.close()
        return
    sess = Session(stick, cloud)
    for target in (sess.cloud_to_stick, sess.stick_to_cloud, sess.poller):
        threading.Thread(target=target, daemon=True).start()
    CURRENT["session"] = sess
    sess.done.wait()
    if CURRENT["session"] is sess:
        CURRENT["session"] = None
    for s in (stick, cloud):
        try:
            s.close()
        except Exception:
            pass
    log(f"CLOSED {addr}")


def local_client(conn, addr):
    log(f"LOCAL CONNECT {addr}")
    conn.settimeout(LOCAL_IDLE_TIMEOUT_S)
    sp = Splitter()
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            for kind, req in sp.feed(data):
                if kind != "frame":
                    continue
                payload = req[11:-2]
                rtu = payload[15:]
                if req[4] != 0x45 or len(payload) < 15 + 8 or payload[0] != 0x02:
                    log(f"LOCAL reject (not a V5 Modbus request): {req.hex()}")
                    continue
                if modbus_crc(rtu[:-2]) != struct.unpack("<H", rtu[-2:])[0] or rtu[1] not in READ_FUNCTIONS:
                    log(f"LOCAL reject (bad CRC or non-read function 0x{rtu[1]:02x}): {rtu.hex(' ')}")
                    continue
                start, count = struct.unpack(">HH", rtu[2:6])
                sess = CURRENT["session"]
                if sess is None or sess.serial is None:
                    log(f"LOCAL fc={rtu[1]:02x} start={start} count={count}: stick not connected")
                    continue
                reply = sess.request(lambda msg_id: sess.build_frame(msg_id, payload))
                if reply is None:
                    log(f"LOCAL fc={rtu[1]:02x} start={start} count={count}: no reply from stick")
                    continue
                out = bytearray(b"\xa5" + reply[1:4] + b"\x15" + req[5:7] + req[7:11] + reply[11:-2] + b"\x00\x15")
                out[-2] = checksum(out)
                conn.sendall(bytes(out))
                log(f"LOCAL fc={rtu[1]:02x} start={start} count={count}: ok")
    except Exception as e:
        log(f"LOCAL client ended {addr}: {e!r}")
    finally:
        conn.close()
        log(f"LOCAL CLOSED {addr}")


def local_server(ls):
    while True:
        c, a = ls.accept()
        if a[0] not in LOCAL_ALLOWED:
            log(f"LOCAL refused {a}")
            c.close()
            continue
        threading.Thread(target=local_client, args=(c, a), daemon=True).start()


ls = socket.socket()
ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ls.bind(LOCAL_LOGGER)
ls.listen(4)
log(f"local logger endpoint on {LOCAL_LOGGER[0]}:{LOCAL_LOGGER[1]} allow={sorted(LOCAL_ALLOWED)}")

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(LISTEN)
threading.Thread(target=local_server, args=(ls,), daemon=True).start()
s.listen(4)
log(f"deye proxy listening on {LISTEN[0]}:{LISTEN[1]} -> {UPSTREAM[0]}:{UPSTREAM[1]} poll={POLL_MODE}")
while True:
    c, a = s.accept()
    threading.Thread(target=handle, args=(c, a), daemon=True).start()
