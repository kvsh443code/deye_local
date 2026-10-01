#!/bin/sh
set -eu
: "${HOTSPOT_IFACE:?}" "${STICK_MAC:?}" "${HOTSPOT_GATEWAY:?}" "${PROXY_PORT:?}" "${UPSTREAM_PORT:?}"
IPT=/usr/sbin/iptables

DNAT="-i $HOTSPOT_IFACE -m mac --mac-source $STICK_MAC -p tcp --dport $UPSTREAM_PORT -j DNAT --to-destination $HOTSPOT_GATEWAY:$PROXY_PORT"
ACCEPT="-i $HOTSPOT_IFACE -m mac --mac-source $STICK_MAC -p tcp --dport $PROXY_PORT -j ACCEPT"
NO_EGRESS="-i $HOTSPOT_IFACE -m mac --mac-source $STICK_MAC -j DROP"

case "${1:-}" in
  up)
    $IPT -t nat -C PREROUTING $DNAT 2>/dev/null || $IPT -t nat -I PREROUTING $DNAT
    $IPT -C INPUT $ACCEPT 2>/dev/null || $IPT -I INPUT $ACCEPT
    $IPT -C FORWARD $NO_EGRESS 2>/dev/null || $IPT -I FORWARD $NO_EGRESS
    ;;
  down)
    while $IPT -t nat -C PREROUTING $DNAT 2>/dev/null; do $IPT -t nat -D PREROUTING $DNAT; done
    while $IPT -C INPUT $ACCEPT 2>/dev/null; do $IPT -D INPUT $ACCEPT; done
    while $IPT -C FORWARD $NO_EGRESS 2>/dev/null; do $IPT -D FORWARD $NO_EGRESS; done
    ;;
  *)
    echo "usage: $0 up|down" >&2
    exit 2
    ;;
esac
