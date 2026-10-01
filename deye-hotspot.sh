#!/bin/sh
set -eu
: "${HOTSPOT_IFACE:?}" "${HOTSPOT_SSID:?}" "${HOTSPOT_PASSWORD:?}"
YAML=/run/netplan/90-deye-hotspot.yaml
CONN="netplan-${HOTSPOT_IFACE}-${HOTSPOT_SSID}"

yaml_quote() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

case "${1:-}" in
  up)
    install -d -m 755 /run/netplan
    umask 077
    cat > "$YAML" <<EOF
network:
  version: 2
  wifis:
    ${HOTSPOT_IFACE}:
      renderer: NetworkManager
      access-points:
        "$(yaml_quote "$HOTSPOT_SSID")":
          mode: ap
          hidden: ${HOTSPOT_HIDDEN:-true}
          band: 2.4GHz
          channel: ${HOTSPOT_CHANNEL:-6}
          password: "$(yaml_quote "$HOTSPOT_PASSWORD")"
          networkmanager:
            passthrough:
              ipv4.method: shared
EOF
    netplan generate
    nmcli connection reload
    nmcli --wait 30 connection up "$CONN"
    ;;
  down)
    nmcli connection down "$CONN" 2>/dev/null || true
    rm -f "$YAML"
    netplan generate
    nmcli connection reload
    nmcli device connect "$HOTSPOT_IFACE" 2>/dev/null || true
    ;;
  *)
    echo "usage: $0 up|down" >&2
    exit 2
    ;;
esac
