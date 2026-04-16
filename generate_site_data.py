"""
Generate realistic Bitcoin mining site telemetry data.
Simulates 14 days of operations for a site with:
- 3 containers (A, B, C) with ~60 miners each (180 total)
- Mixed fleet: Antminer S21, S19 XP, Whatsminer M56S, M63
- Time-of-use electricity pricing (ERCOT-like)
- Ambient temperature cycles (Texas summer)
- Embedded patterns: degradation, failures, anomalies, efficiency variance
"""

import csv
import math
import random
import os
from datetime import datetime, timedelta

random.seed(42)

# --- Miner specs (nominal) ---
MINER_MODELS = {
    "S21":    {"hashrate_th": 200, "power_w": 3500, "efficiency_wth": 17.5},
    "S19XP":  {"hashrate_th": 140, "power_w": 3010, "efficiency_wth": 21.5},
    "M56S":   {"hashrate_th": 212, "power_w": 5400, "efficiency_wth": 25.5},  # hydro
    "M63":    {"hashrate_th": 390, "power_w": 7215, "efficiency_wth": 18.5},
}

# --- Container layout ---
CONTAINERS = {
    "A": {  # newest fleet
        "models": ["S21"] * 40 + ["M63"] * 20,
        "cooling": "air",
        "ambient_offset": 0,  # well-ventilated
    },
    "B": {  # mixed fleet
        "models": ["S19XP"] * 30 + ["S21"] * 20 + ["M56S"] * 10,
        "cooling": "air",
        "ambient_offset": 3,  # slightly hotter (older cooling)
    },
    "C": {  # older fleet, problematic
        "models": ["S19XP"] * 35 + ["S21"] * 15 + ["M63"] * 10,
        "cooling": "air",
        "ambient_offset": 5,  # worst airflow
    },
}

# --- Build miner registry ---
miners = []
miner_id = 0
for container_name, container in CONTAINERS.items():
    for slot_idx, model in enumerate(container["models"]):
        rack = (slot_idx // 10) + 1
        slot = (slot_idx % 10) + 1
        miner_id += 1
        specs = MINER_MODELS[model]
        miners.append({
            "miner_id": f"MNR-{miner_id:04d}",
            "container": container_name,
            "position": f"R{rack}_{slot:02d}",
            "model": model,
            "cooling": container["cooling"],
            "ambient_offset": container["ambient_offset"],
            # Per-miner personality (manufacturing variance)
            "efficiency_factor": random.gauss(1.0, 0.03),  # ±3% from nominal
            "thermal_offset": random.gauss(0, 2),  # ±2°C chip temp variance
            "nominal_hashrate_th": specs["hashrate_th"],
            "nominal_power_w": specs["power_w"],
            "nominal_efficiency_wth": specs["efficiency_wth"],
        })

print(f"Total miners: {len(miners)}")

# --- Define degrading miners (will get worse over 14 days) ---
DEGRADING_MINERS = {
    "MNR-0007": {"rate": 0.008, "type": "efficiency"},    # Container A, S21 — gradual efficiency loss
    "MNR-0023": {"rate": 0.012, "type": "thermal"},        # Container A, M63 — rising temps
    "MNR-0065": {"rate": 0.015, "type": "efficiency"},    # Container B, S19XP — worst degradation
    "MNR-0098": {"rate": 0.006, "type": "hashrate"},       # Container B, M56S — slow hash rate drop
    "MNR-0125": {"rate": 0.010, "type": "thermal"},        # Container C, S19XP — thermal runaway
    "MNR-0145": {"rate": 0.020, "type": "efficiency"},    # Container C, S21 — fast degradation
    "MNR-0170": {"rate": 0.009, "type": "hashrate"},       # Container C, M63 — hash rate decline
}

# --- Define intermittent failure miners ---
FAILING_MINERS = {
    "MNR-0042": [  # Container A — intermittent crashes
        (datetime(2026, 4, 12, 8, 0), datetime(2026, 4, 12, 11, 30)),
        (datetime(2026, 4, 14, 2, 0), datetime(2026, 4, 14, 6, 0)),
        (datetime(2026, 4, 18, 14, 0), datetime(2026, 4, 18, 20, 0)),
    ],
    "MNR-0088": [  # Container B — goes down and stays down
        (datetime(2026, 4, 16, 0, 0), datetime(2026, 4, 22, 0, 0)),
    ],
    "MNR-0155": [  # Container C — frequent short outages
        (datetime(2026, 4, 10, 6, 0), datetime(2026, 4, 10, 8, 0)),
        (datetime(2026, 4, 11, 14, 0), datetime(2026, 4, 11, 16, 0)),
        (datetime(2026, 4, 13, 3, 0), datetime(2026, 4, 13, 5, 0)),
        (datetime(2026, 4, 15, 20, 0), datetime(2026, 4, 16, 2, 0)),
        (datetime(2026, 4, 17, 10, 0), datetime(2026, 4, 17, 14, 0)),
        (datetime(2026, 4, 19, 7, 0), datetime(2026, 4, 19, 12, 0)),
    ],
}

# --- Define anomalous events (sudden, short-lived) ---
ANOMALY_EVENTS = [
    # (miner_id, start, duration_minutes, type, severity)
    ("MNR-0015", datetime(2026, 4, 11, 15, 30), 45, "temp_spike", 1.4),
    ("MNR-0033", datetime(2026, 4, 13, 3, 0), 30, "hash_drop", 0.3),
    ("MNR-0071", datetime(2026, 4, 15, 22, 0), 60, "temp_spike", 1.5),
    ("MNR-0102", datetime(2026, 4, 12, 10, 0), 90, "rejected_shares", 5.0),
    ("MNR-0130", datetime(2026, 4, 17, 8, 0), 120, "power_surge", 1.3),
    ("MNR-0160", datetime(2026, 4, 14, 16, 0), 40, "hash_drop", 0.4),
    # Container-wide event: Container C cooling failure for 2 hours
    ("CONTAINER_C", datetime(2026, 4, 16, 14, 0), 120, "cooling_failure", 1.0),
]

# --- ERCOT-like electricity pricing ---
def get_electricity_price(dt):
    """Time-of-use with weekend discount and occasional spikes."""
    hour = dt.hour
    is_weekend = dt.weekday() >= 5
    day_of_period = (dt - datetime(2026, 4, 9)).days

    # Base price by time of day
    if 6 <= hour < 10:      # morning ramp
        base = 0.045
    elif 10 <= hour < 14:   # midday
        base = 0.055
    elif 14 <= hour < 18:   # peak (summer afternoon)
        base = 0.085
    elif 18 <= hour < 22:   # evening
        base = 0.060
    else:                    # night (off-peak)
        base = 0.028

    # Weekend discount
    if is_weekend:
        base *= 0.7

    # Add some daily variance
    base *= random.gauss(1.0, 0.08)

    # Occasional price spikes (ERCOT-style, ~5% of hours)
    if random.random() < 0.05 and 13 <= hour <= 18:
        base *= random.uniform(2.0, 4.0)

    # A sustained high-price event on day 8-9 (stress test)
    if 7 <= day_of_period <= 8 and 10 <= hour <= 20:
        base *= 1.8

    return round(max(base, 0.015), 4)  # floor at $0.015/kWh


# --- Ambient temperature (Texas April) ---
def get_ambient_temp(dt):
    """Daily sinusoidal cycle with weather variation."""
    hour = dt.hour + dt.minute / 60.0
    day_of_period = (dt - datetime(2026, 4, 9)).days

    # Base daily cycle: peaks at 15:00, low at 05:00
    daily_cycle = 28 + 10 * math.sin((hour - 5) * math.pi / 12)

    # Multi-day weather pattern (warm front days 5-8)
    weather = 3 * math.sin(day_of_period * math.pi / 7)

    # Random noise
    noise = random.gauss(0, 1.5)

    return round(daily_cycle + weather + noise, 1)


# --- Bitcoin economics (relatively stable over 14 days) ---
def get_btc_economics(dt):
    """BTC price and hash price with daily drift."""
    day_of_period = (dt - datetime(2026, 4, 9)).days

    # BTC price: ~$85,000 with ±5% drift
    btc_base = 85000
    btc_drift = 2000 * math.sin(day_of_period * math.pi / 10)
    btc_noise = random.gauss(0, 500)
    btc_price = btc_base + btc_drift + btc_noise

    # Hash price: ~$0.045/TH/day (derived from BTC price, difficulty, block reward)
    # Difficulty adjustment on day 10 (+3%)
    if day_of_period >= 10:
        difficulty_factor = 0.97  # harder = less revenue per TH
    else:
        difficulty_factor = 1.0

    hash_price = 0.045 * (btc_price / btc_base) * difficulty_factor
    hash_price += random.gauss(0, 0.001)

    return round(btc_price, 2), round(max(hash_price, 0.01), 5)


# --- Generate time series ---
START = datetime(2026, 4, 9, 0, 0)
END = datetime(2026, 4, 23, 0, 0)
INTERVAL = timedelta(minutes=5)

timestamps = []
t = START
while t < END:
    timestamps.append(t)
    t += INTERVAL

print(f"Timestamps: {len(timestamps)} ({len(timestamps)*5/60:.0f} hours)")
print(f"Expected rows: {len(timestamps) * len(miners):,}")

# --- Check for anomaly events ---
def is_in_failure(miner_id, dt):
    if miner_id not in FAILING_MINERS:
        return False
    for start, end in FAILING_MINERS[miner_id]:
        if start <= dt < end:
            return True
    return False

def get_anomaly(miner_id, container, dt):
    """Returns (type, severity) or None."""
    for event in ANOMALY_EVENTS:
        eid, estart, eduration, etype, eseverity = event
        eend = estart + timedelta(minutes=eduration)
        if estart <= dt < eend:
            if eid == miner_id:
                return (etype, eseverity)
            if eid == f"CONTAINER_{container}" :
                return (etype, eseverity)
    return None

# --- Generate CSV ---
OUTPUT = os.path.join(os.path.dirname(__file__), "site_telemetry.csv")
ECONOMICS_OUTPUT = os.path.join(os.path.dirname(__file__), "btc_economics.csv")
MINER_REGISTRY = os.path.join(os.path.dirname(__file__), "miner_registry.csv")

# Write miner registry
with open(MINER_REGISTRY, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[
        "miner_id", "container", "position", "model", "cooling",
        "nominal_hashrate_th", "nominal_power_w", "nominal_efficiency_wth",
    ])
    w.writeheader()
    for m in miners:
        w.writerow({k: m[k] for k in w.fieldnames})

print(f"Wrote miner registry: {MINER_REGISTRY}")

# Write BTC economics (hourly)
with open(ECONOMICS_OUTPUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[
        "timestamp", "btc_price_usd", "hash_price_usd_th_day",
        "network_difficulty_t", "block_reward_btc",
    ])
    w.writeheader()
    t = START
    while t < END:
        btc_price, hash_price = get_btc_economics(t)
        day_of_period = (t - START).days
        difficulty = 85.5 if day_of_period < 10 else 88.1  # trillion
        w.writerow({
            "timestamp": t.isoformat(),
            "btc_price_usd": btc_price,
            "hash_price_usd_th_day": hash_price,
            "network_difficulty_t": difficulty,
            "block_reward_btc": 3.125,
        })
        t += timedelta(hours=1)

print(f"Wrote BTC economics: {ECONOMICS_OUTPUT}")

# Write telemetry
row_count = 0
with open(OUTPUT, "w", newline="") as f:
    fieldnames = [
        "timestamp", "miner_id", "container", "position", "model",
        "status", "power_mode",
        "hashrate_th_5m", "hashrate_th_avg",
        "power_w", "efficiency_wth",
        "chip_temp_c", "board_temp_c", "inlet_temp_c",
        "fan_speed_rpm",
        "accepted_shares", "rejected_shares", "stale_shares",
        "frequency_mhz",
        "uptime_hours",
        "electricity_rate_usd_kwh",
    ]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()

    for ts in timestamps:
        ambient = get_ambient_temp(ts)
        elec_rate = get_electricity_price(ts)
        day_of_period = (ts - START).total_seconds() / 86400.0

        for m in miners:
            mid = m["miner_id"]
            specs = MINER_MODELS[m["model"]]

            # --- Check if miner is down ---
            if is_in_failure(mid, ts):
                w.writerow({
                    "timestamp": ts.isoformat(),
                    "miner_id": mid,
                    "container": m["container"],
                    "position": m["position"],
                    "model": m["model"],
                    "status": "offline",
                    "power_mode": "sleep",
                    "hashrate_th_5m": 0,
                    "hashrate_th_avg": 0,
                    "power_w": 15,  # standby power
                    "efficiency_wth": "",
                    "chip_temp_c": "",
                    "board_temp_c": "",
                    "inlet_temp_c": round(ambient + m["ambient_offset"], 1),
                    "fan_speed_rpm": 0,
                    "accepted_shares": 0,
                    "rejected_shares": 0,
                    "stale_shares": 0,
                    "frequency_mhz": 0,
                    "uptime_hours": 0,
                    "electricity_rate_usd_kwh": elec_rate,
                })
                row_count += 1
                continue

            # --- Degradation ---
            deg = DEGRADING_MINERS.get(mid)
            deg_factor = 1.0
            temp_deg = 0
            if deg:
                progress = day_of_period / 14.0  # 0 to 1 over 14 days
                if deg["type"] == "efficiency":
                    deg_factor = 1.0 + deg["rate"] * day_of_period  # efficiency gets worse
                elif deg["type"] == "thermal":
                    temp_deg = deg["rate"] * day_of_period * 3  # temp rises
                elif deg["type"] == "hashrate":
                    deg_factor = 1.0  # efficiency same, but hash rate drops
                    # handled below

            # --- Base calculations ---
            inlet_temp = round(ambient + m["ambient_offset"] + random.gauss(0, 0.5), 1)

            # Hash rate
            hr_base = specs["hashrate_th"] * m["efficiency_factor"]
            if deg and deg["type"] == "hashrate":
                hr_base *= (1.0 - deg["rate"] * day_of_period)

            # Thermal effect on hash rate (throttle above 40°C ambient)
            effective_ambient = inlet_temp
            if effective_ambient > 40:
                thermal_throttle = 1.0 - (effective_ambient - 40) * 0.02
                hr_base *= max(thermal_throttle, 0.7)

            # Add noise
            hashrate_5m = max(0, hr_base + random.gauss(0, hr_base * 0.015))
            hashrate_avg = max(0, hr_base + random.gauss(0, hr_base * 0.008))

            # Power
            power_base = specs["power_w"] * m["efficiency_factor"] * deg_factor
            power = max(100, power_base + random.gauss(0, power_base * 0.01))

            # Efficiency
            efficiency = power / hashrate_5m if hashrate_5m > 0 else 999

            # Temperatures
            chip_temp = (
                60  # base chip temp
                + (inlet_temp - 25) * 0.8  # ambient influence
                + m["thermal_offset"]
                + temp_deg
                + (power / specs["power_w"] - 1) * 15  # power correlation
                + random.gauss(0, 1.0)
            )
            board_temp = chip_temp - random.uniform(5, 10)

            # Fan speed (scales with chip temp)
            fan_base = 3500 + (chip_temp - 55) * 80
            fan_speed = max(1000, min(6500, fan_base + random.gauss(0, 100)))

            # Shares (per 5-min interval)
            share_rate = hashrate_5m / 50  # rough approximation
            accepted = max(0, int(share_rate + random.gauss(0, share_rate * 0.05)))
            reject_rate = 0.01 + random.expovariate(200)  # ~1% base + rare spikes
            rejected = max(0, int(accepted * reject_rate))
            stale = max(0, int(accepted * random.uniform(0.001, 0.005)))

            # Frequency
            freq_base = 500 + (hashrate_5m / specs["hashrate_th"] - 1) * 50
            frequency = max(300, freq_base + random.gauss(0, 5))

            # Uptime (hours since last restart, increases over time)
            uptime_base = day_of_period * 24
            uptime = max(0, uptime_base + random.gauss(0, 2))

            status = "mining"
            power_mode = "normal"

            # --- Apply anomalies ---
            anomaly = get_anomaly(mid, m["container"], ts)
            if anomaly:
                atype, aseverity = anomaly
                if atype == "temp_spike":
                    chip_temp *= aseverity
                    board_temp *= aseverity
                    fan_speed = min(6500, fan_speed * 1.3)
                    status = "mining"  # still mining but dangerously hot
                elif atype == "hash_drop":
                    hashrate_5m *= aseverity
                    hashrate_avg *= aseverity
                    efficiency = power / hashrate_5m if hashrate_5m > 0 else 999
                    status = "error"
                elif atype == "rejected_shares":
                    rejected = int(accepted * aseverity * 0.1)  # 50% rejection
                    status = "mining"
                elif atype == "power_surge":
                    power *= aseverity
                    efficiency = power / hashrate_5m if hashrate_5m > 0 else 999
                elif atype == "cooling_failure":
                    chip_temp += 15  # all miners in container get hot
                    board_temp += 12
                    fan_speed = 6500  # fans maxed out
                    if chip_temp > 90:
                        hashrate_5m *= 0.7  # thermal throttling
                        hashrate_avg *= 0.75
                        status = "error"

            # --- Introduce some missing data (1% of readings) ---
            has_gap = random.random() < 0.01

            w.writerow({
                "timestamp": ts.isoformat(),
                "miner_id": mid,
                "container": m["container"],
                "position": m["position"],
                "model": m["model"],
                "status": status,
                "power_mode": power_mode,
                "hashrate_th_5m": "" if has_gap else round(hashrate_5m, 2),
                "hashrate_th_avg": "" if has_gap else round(hashrate_avg, 2),
                "power_w": "" if has_gap else round(power, 1),
                "efficiency_wth": "" if has_gap else round(efficiency, 2),
                "chip_temp_c": "" if has_gap else round(chip_temp, 1),
                "board_temp_c": "" if has_gap else round(board_temp, 1),
                "inlet_temp_c": round(inlet_temp, 1),
                "fan_speed_rpm": "" if has_gap else round(fan_speed),
                "accepted_shares": "" if has_gap else accepted,
                "rejected_shares": "" if has_gap else rejected,
                "stale_shares": "" if has_gap else stale,
                "frequency_mhz": "" if has_gap else round(frequency, 1),
                "uptime_hours": round(uptime, 1),
                "electricity_rate_usd_kwh": elec_rate,
            })
            row_count += 1

            if row_count % 500000 == 0:
                print(f"  {row_count:,} rows written...")

print(f"\nDone. Wrote {row_count:,} rows to {OUTPUT}")
print(f"File size: {os.path.getsize(OUTPUT) / 1024 / 1024:.1f} MB")
