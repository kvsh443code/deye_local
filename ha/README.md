# Home Assistant profile

The Solarman Stick Logger integration by davidrapan is installed through HACS. Version 25.08.16 was used. The repository is shown below.

```text
https://github.com/davidrapan/ha-solarman
```

In HACS the repository named Solarman with the description Solarman Stick Logger integration is downloaded. Home Assistant is restarted after the download.

The profile in this folder is a copy of deye_hybrid.yaml from that version. The model name is changed and the update intervals are raised to 30 seconds.

The profile is copied into the custom profile folder of the integration. The folder is created first if it does not exist.

```text
/config/custom_components/solarman/inverter_definitions/custom/deye_offgrid.yaml
```

Home Assistant is restarted again so the profile is picked up. It is then listed in the profile selection as custom/deye_offgrid.yaml.

The custom folder sits inside the integration folder, so it may be removed when the integration is updated through HACS. The file is checked after each update and copied again if it is missing.

The integration is added under Settings and then Devices and Services. The values below are entered. They are taken from the .env file of the proxy.

```text
Host       LOCAL_BIND
Port       LOCAL_PORT
Serial     LOGGER_SERIAL
Transport  TCP
Profile    custom/deye_offgrid.yaml
```

The address of Home Assistant has to be listed in LOCAL_ALLOW or the connection is refused by the proxy.
