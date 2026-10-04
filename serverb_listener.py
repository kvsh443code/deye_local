import socket, threading, datetime, sys

from settings import setting

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
LOG = open(f"{setting('LOG_DIR')}/serverb-capture.log", "a", buffering=1)


def log(m):
    LOG.write(f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} {m}\n")


def handle(c, a):
    log(f"CONNECT {a}")
    c.settimeout(float(setting("STICK_IDLE_TIMEOUT_S")))
    try:
        while True:
            d = c.recv(4096)
            if not d:
                break
            kind = "TLS" if d[:2] == b"\x16\x03" else ("SOLARMAN-V5" if d[:1] == b"\xa5" else "?")
            log(f"RX {len(d)}B [{kind}] {d.hex(' ')}")
    except Exception as e:
        log(f"ERR {a} {e!r}")
    finally:
        c.close()
        log(f"CLOSED {a}")


s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", PORT))
s.listen(8)
log(f"listening on {PORT}")
while True:
    c, a = s.accept()
    threading.Thread(target=handle, args=(c, a), daemon=True).start()
