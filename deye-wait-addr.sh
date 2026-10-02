#!/bin/sh
set -eu
: "${LOCAL_BIND:?}" "${HOTSPOT_GATEWAY:?}" "${ADDR_WAIT_TIMEOUT_S:?}"

has_addr() { ip -o -4 addr show | grep -qF " inet $1/"; }

i=0
until has_addr "$LOCAL_BIND" && has_addr "$HOTSPOT_GATEWAY"; do
  i=$((i + 1))
  if [ "$i" -gt "$ADDR_WAIT_TIMEOUT_S" ]; then
    echo "addresses not ready after ${ADDR_WAIT_TIMEOUT_S}s: $LOCAL_BIND $HOTSPOT_GATEWAY" >&2
    exit 1
  fi
  sleep 1
done
