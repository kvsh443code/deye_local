#!/bin/sh
set -eu
: "${HOTSPOT_IFACE:?}" "${HOTSPOT_SSID:?}" "${HOTSPOT_PASSWORD:?}" "${HOTSPOT_HIDDEN:?}" "${HOTSPOT_BAND:?}" "${HOTSPOT_CHANNEL:?}"
YAML=/run/netplan/90-deye-hotspot.yaml
NETPLAN_ID=deye-hotspot
CONN="netplan-${NETPLAN_ID}-${HOTSPOT_SSID}"

yaml_quote() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

case "${1:-}" in
  up)
    install -d -m 755 /run/netplan
    umask 077
    cat > "$YAML" <<EOF
network:
  version: 2
  wifis:
    ${NETPLAN_ID}:
      renderer: NetworkManager
      match:
        name: "$(yaml_quote "$HOTSPOT_IFACE")"
      access-points:
        "$(yaml_quote "$HOTSPOT_SSID")":
          mode: ap
          hidden: ${HOTSPOT_HIDDEN}
          band: ${HOTSPOT_BAND}
          channel: ${HOTSPOT_CHANNEL}
          password: "$(yaml_quote "$HOTSPOT_PASSWORD")"
          networkmanager:
            passthrough:
              ipv4.method: shared
EOF
    netplan generate
    nmcli connection reload
    i=0
    until nmcli -t -f NAME connection show | grep -qxF "$CONN"; do
      i=$((i + 1))
      [ "$i" -le 30 ] || { echo "NetworkManager did not load $CONN" >&2; exit 1; }
      sleep 1
    done
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
