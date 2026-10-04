import socket, ssl, threading, datetime, struct, time

from settings import setting

LOG_DIR = setting("LOG_DIR")
CONF_DIR = setting("CONF_DIR")
LISTEN = (setting("HOTSPOT_GATEWAY"), int(setting("PROXY_PORT")))
LOG = open(f"{LOG_DIR}/local-cloud.log", "a", buffering=1)
DATA = open(f"{LOG_DIR}/local-cloud-frames.hex", "a", buffering=1)
TYPES = {0x41: "HANDSHAKE", 0x42: "DATA", 0x43: "WIFI", 0x47: "HEARTBEAT", 0x48: "TYPE48"}


def log(m):
    LOG.write(f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} {m}\n")


def checksum(frame):
    return sum(frame[1:-2]) & 0xFF


def build_response(hdr, payload):
    resp = bytearray(23)
    resp[0] = 0xA5
    struct.pack_into("<H", resp, 1, 10)
    resp[3] = hdr[3]
    resp[4] = (hdr[4] - 0x30) & 0xFF
    resp[5] = (hdr[5] + 1) & 0xFF
    resp[6] = hdr[6]
    resp[7:11] = hdr[7:11]
    resp[11] = payload[0] if payload else 0
    resp[12] = 0x01
    struct.pack_into("<I", resp, 13, int(time.time()))
    struct.pack_into("<I", resp, 17, 0)
    resp[21] = checksum(resp)
    resp[22] = 0x15
    return bytes(resp)


ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
ctx.set_ciphers("ALL:@SECLEVEL=0")
ctx.load_cert_chain(f"{CONF_DIR}/mitm-cert.pem", f"{CONF_DIR}/mitm-key.pem")


def handle(raw, addr):
    log(f"CONNECT {addr}")
    raw.settimeout(float(setting("STICK_IDLE_TIMEOUT_S")))
    try:
        tls = ctx.wrap_socket(raw, server_side=True)
    except Exception as e:
        log(f"HANDSHAKE FAILED {addr}: {e!r}")
        raw.close()
        return
    log(f"TLS OK {addr}: {tls.cipher()[0]}")
    buf = b""
    try:
        while True:
            chunk = tls.recv(8192)
            if not chunk:
                break
            buf += chunk
            while len(buf) >= 13:
                if buf[0] != 0xA5:
                    log(f"resync: dropping byte {buf[0]:02x}")
                    buf = buf[1:]
                    continue
                plen = struct.unpack_from("<H", buf, 1)[0]
                flen = 11 + plen + 2
                if len(buf) < flen:
                    break
                frame, buf = buf[:flen], buf[flen:]
                hdr, payload = frame[:11], frame[11:-2]
                ftype = frame[4]
                ok = checksum(frame) == frame[-2] and frame[-1] == 0x15
                name = TYPES.get(ftype, f"0x{ftype:02x}")
                log(f"RX {name} len={flen} seq={frame[5]:02x}/{frame[6]:02x} schema={payload[1] if len(payload) > 1 else -1:02x} csum={'ok' if ok else 'BAD'}")
                DATA.write(f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} {name} {frame.hex()}\n")
                tls.sendall(build_response(hdr, payload))
    except Exception as e:
        log(f"read ended {addr}: {e!r}")
    finally:
        try:
            tls.close()
        except Exception:
            pass
        log(f"CLOSED {addr}")


s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(LISTEN)
s.listen(4)
log(f"local cloud listening on {LISTEN[0]}:{LISTEN[1]}")
while True:
    c, a = s.accept()
    threading.Thread(target=handle, args=(c, a), daemon=True).start()
