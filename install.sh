#!/bin/sh
set -eu
cd "$(dirname "$0")"

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
[ -f .env ] || { echo "missing .env (copy .env.example and fill it in)" >&2; exit 1; }
set -a; . ./.env; set +a

for v in HOTSPOT_IFACE HOTSPOT_SSID HOTSPOT_PASSWORD HOTSPOT_GATEWAY STICK_MAC LOGGER_SERIAL \
         PROXY_PORT UPSTREAM_HOST UPSTREAM_PORT IGEN_CA_SHA256 LOCAL_BIND LOCAL_PORT LOCAL_ALLOW \
         ADDR_WAIT_TIMEOUT_S SERVICE_USER INSTALL_DIR CONF_DIR LOG_DIR; do
  eval "val=\${$v:-}"
  [ -n "$val" ] || { echo "missing $v in .env" >&2; exit 1; }
done

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  if getent group "$SERVICE_USER" >/dev/null; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin -g "$SERVICE_USER" "$SERVICE_USER"
  else
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$SERVICE_USER"
  fi
fi
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
  usermod -aG "$SERVICE_USER" "$SUDO_USER"
fi

install -d -o root -g root -m 755 "$INSTALL_DIR"
install -o root -g root -m 644 deye_proxy.py settings.py register_map.py "$INSTALL_DIR/"
install -o root -g root -m 755 deye-fw.sh deye-hotspot.sh deye-wait-addr.sh "$INSTALL_DIR/"

install -d -o root -g "$SERVICE_USER" -m 750 "$CONF_DIR"
install -o root -g "$SERVICE_USER" -m 640 .env "$CONF_DIR/deye-proxy.env"

if [ ! -f "$CONF_DIR/mitm-key.pem" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=deye-proxy" \
    -keyout "$CONF_DIR/mitm-key.pem" -out "$CONF_DIR/mitm-cert.pem" 2>/dev/null
  chown root:"$SERVICE_USER" "$CONF_DIR/mitm-key.pem" "$CONF_DIR/mitm-cert.pem"
  chmod 640 "$CONF_DIR/mitm-key.pem"
  chmod 644 "$CONF_DIR/mitm-cert.pem"
fi

if [ ! -f "$CONF_DIR/igen-ca.pem" ]; then
  tmp=$(mktemp)
  timeout 20 openssl s_client -connect "$UPSTREAM_HOST:$UPSTREAM_PORT" -servername "$UPSTREAM_HOST" -showcerts </dev/null 2>/dev/null \
    | awk '/BEGIN CERTIFICATE/{n++; buf=""} n{buf=buf $0 "\n"} /END CERTIFICATE/{last=buf} END{printf "%s", last}' > "$tmp"
  fp=$(openssl x509 -in "$tmp" -noout -fingerprint -sha256 | cut -d= -f2)
  if [ "$fp" != "$IGEN_CA_SHA256" ]; then
    rm -f "$tmp"
    echo "IGEN CA fingerprint mismatch: got $fp, expected $IGEN_CA_SHA256" >&2
    exit 1
  fi
  install -o root -g "$SERVICE_USER" -m 644 "$tmp" "$CONF_DIR/igen-ca.pem"
  rm -f "$tmp"
fi

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 750 "$LOG_DIR"

render() {
  sed -e "s|@SERVICE_USER@|$SERVICE_USER|g" -e "s|@INSTALL_DIR@|$INSTALL_DIR|g" \
      -e "s|@CONF_DIR@|$CONF_DIR|g" -e "s|@LOG_DIR@|$LOG_DIR|g" "$1"
}
render deye-hotspot.service > /etc/systemd/system/deye-hotspot.service
render deye-proxy.service > /etc/systemd/system/deye-proxy.service
render deye-proxy.logrotate > /etc/logrotate.d/deye-proxy
chmod 644 /etc/systemd/system/deye-hotspot.service /etc/systemd/system/deye-proxy.service /etc/logrotate.d/deye-proxy

systemctl daemon-reload
systemctl enable deye-hotspot.service deye-proxy.service
systemctl restart deye-hotspot.service deye-proxy.service
systemctl --no-pager --lines=5 status deye-hotspot.service deye-proxy.service || true
