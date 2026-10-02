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
    22: ("clock_year_month", "", 1, False),
    23: ("clock_day_hour", "", 1, False),
    24: ("clock_minute_second", "", 1, False),
    200: ("battery_type", "", 1, False),
    201: ("equalization_voltage", "V", 0.01, False),
    202: ("absorption_voltage", "V", 0.01, False),
    203: ("float_voltage", "V", 0.01, False),
    204: ("battery_capacity", "Ah", 1, False),
    205: ("battery_empty_voltage", "V", 0.01, False),
    206: ("zero_export_power", "W", 1, False),
    207: ("equalization_cycle", "d", 1, False),
    208: ("equalization_time", "h", 0.5, False),
    209: ("tempco", "mV/C/cell", 1, False),
    210: ("max_charge_current", "A", 1, False),
    211: ("max_discharge_current", "A", 1, False),
    214: ("activate_battery", "", 1, False),
    215: ("battery_resistance", "mOhm", 1, False),
    216: ("charge_efficiency", "%", 0.1, False),
    217: ("shutdown_soc", "%", 1, False),
    218: ("restart_soc", "%", 1, False),
    219: ("low_soc", "%", 1, False),
    220: ("shutdown_voltage", "V", 0.01, False),
    221: ("restart_voltage", "V", 0.01, False),
    222: ("low_voltage", "V", 0.01, False),
    225: ("gen_start_voltage", "V", 0.01, False),
    226: ("gen_start_soc", "%", 1, False),
    227: ("gen_charge_current", "A", 1, False),
    228: ("grid_start_voltage", "V", 0.01, False),
    229: ("grid_start_soc", "%", 1, False),
    230: ("grid_charge_current", "A", 1, False),
    231: ("gen_charge_enable", "", 1, False),
    232: ("grid_charge_enable", "", 1, False),
    235: ("gen_port_mode", "", 1, False),
    236: ("smartload_off_voltage", "V", 0.01, False),
    237: ("smartload_off_soc", "%", 1, False),
    238: ("smartload_on_voltage", "V", 0.01, False),
    239: ("smartload_on_soc", "%", 1, False),
    242: ("charging_signal_flags", "", 1, False),
    243: ("energy_pattern", "", 1, False),
    244: ("work_mode", "", 1, False),
    245: ("max_sell_power", "W", 1, False),
    248: ("tou_enable", "", 1, False),
    250: ("tou1_start_hhmm", "", 1, False),
    251: ("tou2_start_hhmm", "", 1, False),
    252: ("tou3_start_hhmm", "", 1, False),
    253: ("tou4_start_hhmm", "", 1, False),
    254: ("tou5_start_hhmm", "", 1, False),
    255: ("tou6_start_hhmm", "", 1, False),
    256: ("tou1_power", "W", 1, False),
    257: ("tou2_power", "W", 1, False),
    258: ("tou3_power", "W", 1, False),
    259: ("tou4_power", "W", 1, False),
    260: ("tou5_power", "W", 1, False),
    261: ("tou6_power", "W", 1, False),
    262: ("tou1_battery_voltage", "V", 0.01, False),
    263: ("tou2_battery_voltage", "V", 0.01, False),
    264: ("tou3_battery_voltage", "V", 0.01, False),
    265: ("tou4_battery_voltage", "V", 0.01, False),
    266: ("tou5_battery_voltage", "V", 0.01, False),
    267: ("tou6_battery_voltage", "V", 0.01, False),
    268: ("tou1_soc", "%", 1, False),
    269: ("tou2_soc", "%", 1, False),
    270: ("tou3_soc", "%", 1, False),
    271: ("tou4_soc", "%", 1, False),
    272: ("tou5_soc", "%", 1, False),
    273: ("tou6_soc", "%", 1, False),
    274: ("tou1_flags", "", 1, False),
    275: ("tou2_flags", "", 1, False),
    276: ("tou3_flags", "", 1, False),
    277: ("tou4_flags", "", 1, False),
    278: ("tou5_flags", "", 1, False),
    279: ("tou6_flags", "", 1, False),
    292: ("gen_peak_shaving_power", "W", 1, False),
    293: ("grid_peak_shaving_power", "W", 1, False),
    327: ("ct_ratio", "", 1, False),
    330: ("basic_flags", "", 1, False),
}


def describe(reg, raw):
    entry = LIVE.get(reg) or SETTINGS.get(reg)
    if entry is None:
        return f"{reg} raw {raw}"
    name, unit, scale, signed = entry
    value = raw - 65536 if signed and raw > 32767 else raw
    return f"{reg} {name} {round(value * scale, 2)} {unit}".rstrip()


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
