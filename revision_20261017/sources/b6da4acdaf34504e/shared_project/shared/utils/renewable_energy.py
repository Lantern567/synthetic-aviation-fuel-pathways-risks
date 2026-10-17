from math import isfinite


def power_to_energy_mwh(power_mw, duration_hours):
    power = float(power_mw)
    duration = float(duration_hours)
    if not isfinite(power) or power < 0:
        raise ValueError(f'可再生功率必须为有限非负数，收到 {power_mw!r} MW')
    if not isfinite(duration) or duration <= 0:
        raise ValueError(f'时段长度必须为有限正数，收到 {duration_hours!r} 小时')
    return power * duration


def energy_to_mean_power_mw(energy_mwh, duration_hours):
    energy = float(energy_mwh)
    duration = float(duration_hours)
    if not isfinite(energy) or energy < 0:
        raise ValueError(f'可再生电量必须为有限非负数，收到 {energy_mwh!r} MWh')
    if not isfinite(duration) or duration <= 0:
        raise ValueError(f'时段长度必须为有限正数，收到 {duration_hours!r} 小时')
    return energy / duration
