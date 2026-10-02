#!/bin/sh
set -eu
cd "$(dirname "$0")"

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

ENV="$(pwd)/.env"
[ -f "$ENV" ] || ENV=/etc/deye-proxy/deye-proxy.env
[ -f "$ENV" ] || { echo "no .env here and no installed env file; nothing to read settings from" >&2; exit 1; }
set -a; . "$ENV"; set +a

systemctl disable --now deye-proxy.service deye-hotspot.service 2>/dev/null || true

if [ -x "$INSTALL_DIR/deye-fw.sh" ]; then "$INSTALL_DIR/deye-fw.sh" down || true; fi
if [ -n "${HOTSPOT_IFACE:-}" ] && [ -n "${HOTSPOT_SSID:-}" ]; then
  nmcli connection down "netplan-deye-hotspot-${HOTSPOT_SSID}" 2>/dev/null || true
fi
rm -f /run/netplan/90-deye-hotspot.yaml
netplan generate
nmcli connection reload
[ -n "${HOTSPOT_IFACE:-}" ] && { nmcli device connect "$HOTSPOT_IFACE" 2>/dev/null || true; }

rm -f /etc/systemd/system/deye-proxy.service /etc/systemd/system/deye-hotspot.service /etc/logrotate.d/deye-proxy
systemctl daemon-reload
systemctl reset-failed deye-proxy.service deye-hotspot.service 2>/dev/null || true

rm -rf "$INSTALL_DIR" "$CONF_DIR"

if [ "$PURGE" -eq 1 ]; then
  rm -rf "$LOG_DIR"
  if id "$SERVICE_USER" >/dev/null 2>&1; then userdel "$SERVICE_USER"; fi
  if getent group "$SERVICE_USER" >/dev/null; then groupdel "$SERVICE_USER"; fi
  echo "removed services, files, logs and user $SERVICE_USER"
else
  echo "removed services and files; logs kept in $LOG_DIR (use --purge to remove them and user $SERVICE_USER)"
fi
