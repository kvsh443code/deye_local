LIVE = {
    61: ("battery_temperature", "°C", 0.1, False),
    85: ("load_energy_total", "kWh", 0.1, False),
    96: ("pv_energy_total", "kWh", 0.1, False),
    108: ("pv_energy_today", "kWh", 0.1, False),
    109: ("pv1_voltage", "V", 0.1, False),
    110: ("pv1_current", "A", 0.1, False),
    141: ("load_power", "W", 1, False),
    143: ("battery_voltage_alt", "V", 0.01, False),
    149: ("grid_voltage", "V", 0.1, False),
    170: ("ct_power", "W", 1, True),
    173: ("inverter_output_power", "W", 1, False),
    183: ("battery_voltage", "V", 0.01, False),
    184: ("battery_soc", "%", 1, False),
    186: ("pv1_power", "W", 1, False),
    190: ("battery_power", "W", 1, True),
    191: ("battery_current", "A", 0.01, True),
    192: ("output_frequency", "Hz", 0.01, False),
}

SETTINGS = {
    201: ("equalization_voltage", "V", 0.01, False),
    202: ("absorption_voltage", "V", 0.01, False),
    203: ("float_voltage", "V", 0.01, False),
    250: ("tou1_start_hhmm", "", 1, False),
    251: ("tou2_start_hhmm", "", 1, False),
    252: ("tou3_start_hhmm", "", 1, False),
    253: ("tou4_start_hhmm", "", 1, False),
    254: ("tou5_start_hhmm", "", 1, False),
    255: ("tou6_start_hhmm", "", 1, False),
    262: ("tou1_battery_voltage", "V", 0.01, False),
    263: ("tou2_battery_voltage", "V", 0.01, False),
    264: ("tou3_battery_voltage", "V", 0.01, False),
    265: ("tou4_battery_voltage", "V", 0.01, False),
    266: ("tou5_battery_voltage", "V", 0.01, False),
    267: ("tou6_battery_voltage", "V", 0.01, False),
}


def decode(raw, table=LIVE):
    out = {}
    for reg, (name, unit, scale, signed) in table.items():
        v = raw.get(reg, raw.get(str(reg)))
        if not isinstance(v, int):
            continue
        if signed and v > 32767:
            v -= 65536
        out[name] = round(v * scale, 2)
    return out
