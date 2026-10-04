import socket, ssl, threading, datetime

from settings import setting

LOG_DIR = setting("LOG_DIR")
CONF_DIR = setting("CONF_DIR")
LISTEN = (setting("HOTSPOT_GATEWAY"), int(setting("PROXY_PORT")))
LOG = open(f"{LOG_DIR}/mitm-test.log", "a", buffering=1)


def log(m):
    LOG.write(f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} {m}\n")


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
        log(f"HANDSHAKE FAILED {addr}: {e!r}  -> stick rejected our certificate (or cipher mismatch)")
        raw.close()
        return
    log(f"HANDSHAKE OK {addr}: {tls.version()} {tls.cipher()}  -> stick ACCEPTS an untrusted certificate")
    try:
        while True:
            d = tls.recv(4096)
            if not d:
                break
            log(f"DECRYPTED {len(d)}B: {d.hex(' ')}")
    except Exception as e:
        log(f"read ended {addr}: {e!r}")
    finally:
        tls.close()
        log(f"CLOSED {addr}")


s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(LISTEN)
s.listen(4)
log(f"mitm test listening on {LISTEN[0]}:{LISTEN[1]}")
while True:
    c, a = s.accept()
    threading.Thread(target=handle, args=(c, a), daemon=True).start()
