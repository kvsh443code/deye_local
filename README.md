# Deye SUN-6K-OG02LP1-EU-AM1 local proxy

## Install

The example settings are copied to .env and filled in.

```bash
cp .env.example .env
nano .env
```

The installer is run from this folder.

```bash
sudo ./install.sh
```

The service user is created and the installing user is added to its group. The files are installed and both services are started. A new login is needed before the logs can be read through that group.

After a git pull the installer is run again and both services are restarted.

```bash
git pull
sudo ./install.sh
```

## Uninstall

The services and files are removed and the logs are kept.

```bash
sudo ./uninstall.sh
```

Everything is removed including the logs and the service user.

```bash
sudo ./uninstall.sh --purge
```

## Cloud writes

Writes from the cloud to the inverter are passed through when CLOUD_WRITES is set to allow in .env. When it is set to block, only cloud reads reach the inverter, and every other cloud command is dropped and logged as BLOCKED in deye-cloud-reads.log. Settings cannot be changed from DeyeCloud while writes are blocked. Nothing is sent back for a blocked write, so the cloud sends it once more and the app then reports a timeout. The installer is run again after the setting is changed.

Reads from Home Assistant on the local port are always read only.

## Logs

Logs are written to the LOG_DIR folder set in .env. The default folder is used in the paths below. Each log is rotated daily and compressed, and LOG_KEEP_DAYS sets how many days are kept. The default of 92 keeps about three months.

Connections from the stick, the cloud and Home Assistant are logged here.

```bash
tail -f /var/log/deye-proxy/deye-proxy.log
```

Every frame is logged here in both directions after decryption.

```bash
tail -f /var/log/deye-proxy/deye-proxy-frames.hex
```

Every register value read by the cloud is logged here with its name where it is known. Any cloud request that is not a read is logged here too.

```bash
tail -F /var/log/deye-proxy/deye-cloud-reads.log
```

Service output and errors are shown by systemd.

```bash
journalctl -u deye-proxy -u deye-hotspot -f
```

Output is limited to the last boot.

```bash
journalctl -b -u deye-proxy -u deye-hotspot
```

## Status

The state of both services is shown.

```bash
systemctl status deye-hotspot deye-proxy
```

The wifi profile that is using the card is shown.

```bash
nmcli connection show --active
```

Open connections from the stick, the cloud and Home Assistant are listed.

```bash
ss -tn state established '( sport = :10443 or dport = :10443 or sport = :8899 )'
```

The firewall rules added by the service are listed.

```bash
sudo iptables -t nat -S PREROUTING | grep 10443
sudo iptables -S FORWARD | grep DROP
```
