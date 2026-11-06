"""Golf shot and handicap calculations (HW4 tools plus two new ones for HW5).

Pure functions with no MCP code: server.py wraps them as tools. Every function checks
its inputs and raises ValueError instead of returning a plausible-looking number.
"""

import math
import re

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq, minimize

G = 9.81                                  # m/s²
BALL_MASS_KG = 0.04593                    # USGA maximum mass
BALL_RADIUS_M = 0.04267 / 2               # USGA minimum diameter
BALL_AREA_M2 = math.pi * BALL_RADIUS_M**2
MPH, YD, FT = 0.44704, 0.9144, 0.3048     # unit → SI

# TrackMan PGA Tour averages, 2023 season (TrackMan, May 2024).
# club: (ball speed mph, launch deg, backspin rpm, carry yd)
TOUR = {
    "driver": (171, 10.4, 2545, 282), "3-wood": (162, 9.3, 3663, 249),
    "5-wood": (156, 9.7, 4322, 236),  "hybrid": (149, 10.2, 4587, 231),
    "3-iron": (145, 10.3, 4404, 218), "4-iron": (140, 10.8, 4782, 209),
    "5-iron": (135, 11.9, 5280, 199), "6-iron": (130, 14.0, 6204, 188),
    "7-iron": (123, 16.1, 7124, 176), "8-iron": (118, 17.8, 8078, 164),
    "9-iron": (112, 20.0, 8793, 152), "pw":     (104, 23.7, 9316, 142),
}
AERO = (0.225, 0.293, 0.486, 0.423)       # drag/lift constants fitted in HW4 (held-out error 2.2%)

DEFAULT_BAG = [  # my stock carries (yd); driver and 7-iron measured, the rest estimated
    ("driver", 290), ("3-wood", 260), ("5-wood", 245), ("hybrid", 230), ("4-iron", 196),
    ("5-iron", 184), ("6-iron", 172), ("7-iron", 160), ("8-iron", 148), ("9-iron", 136), ("pw", 110),
]

PHYSICS_SCOPE = "point-mass ball, pure backspin, constant spin, uniform wind; carry only, no roll"


def check_range(name, value, low, high):
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value) or not low <= value <= high):
        raise ValueError(f"{name} must be a number from {low} to {high}; got {value!r}")


def air_density(temperature_f, altitude_ft):
    """Dry-air density (kg/m³): standard-atmosphere pressure at altitude, ideal gas at temperature."""
    temp_k = (temperature_f - 32) * 5 / 9 + 273.15
    pressure_pa = 101325 * (1 - 2.25577e-5 * altitude_ft * FT) ** 5.25588
    return pressure_pa / (287.05 * temp_k)


RHO_STOCK = air_density(70, 0)


def flight(ball_speed_mph, launch_deg, spin_rpm, rho, headwind_mph=0.0,
           crosswind_mph=0.0, landing_height_ft=0.0, max_step=0.01):
    """Integrate the flight. Axes: x down the target line, y to the right, z up."""
    a, b, c, d = AERO
    omega = spin_rpm * 2 * math.pi / 60
    wind_x, wind_y = -headwind_mph * MPH, crosswind_mph * MPH  # headwind blows back at the golfer

    def rhs(t, s):
        vx, vy, vz = s[3:]
        ux, uy, uz = vx - wind_x, vy - wind_y, vz              # velocity relative to the air
        u = math.sqrt(ux * ux + uy * uy + uz * uz)
        spin_ratio = BALL_RADIUS_M * omega / u
        cd, cl = a + b * spin_ratio, c * spin_ratio ** d
        k = 0.5 * rho * BALL_AREA_M2 * u / BALL_MASS_KG
        # Backspin axis points left (-y), so lift acts along (-uz, 0, ux).
        return [vx, vy, vz, -k * (cd * ux + cl * uz), -k * cd * uy, -k * (cd * uz - cl * ux) - G]

    landing_m = landing_height_ft * FT
    lands = lambda t, s: s[2] - landing_m
    lands.terminal, lands.direction = True, -1
    theta = math.radians(launch_deg)
    v0 = ball_speed_mph * MPH
    sol = solve_ivp(rhs, (0, 15), [0, 0, 0, v0 * math.cos(theta), 0, v0 * math.sin(theta)],
                    events=lands, max_step=max_step, rtol=1e-8)
    if not sol.t_events[0].size:
        raise ValueError("The ball never comes down to that landing elevation.")
    x, y, _, vx, vy, vz = sol.y_events[0][0]
    return {
        "carry_yd": x / YD,
        "lateral_drift_yd": y / YD,
        "apex_yd": max(sol.y[2]) / YD,
        "hang_time_s": float(sol.t_events[0][0]),
        "landing_angle_deg": math.degrees(math.atan2(-vz, math.hypot(vx, vy))),
    }


CLUB_ALIASES = {"dr": "driver", "1-wood": "driver", "rescue": "hybrid", "hy": "hybrid",
                "pitching-wedge": "pw", "p": "pw", "wedge": "pw"}


def club_key(club):
    """Map '7 iron', '7i', '3W' and similar to a key in TOUR."""
    key = str(club).strip().lower().replace("_", "-").replace(" ", "-")
    key = re.sub(r"^(\d)-?i(ron)?$", r"\1-iron", key)
    key = re.sub(r"^(\d)-?w(ood)?$", r"\1-wood", key)
    key = CLUB_ALIASES.get(key, key)
    if key not in TOUR:
        raise ValueError(f"club must be one of {', '.join(TOUR)}; got {club!r}")
    return key


def check_conditions(headwind_mph, crosswind_mph, temperature_f, altitude_ft, elevation_change_ft=0.0):
    check_range("headwind_mph", headwind_mph, -40, 40)
    check_range("crosswind_mph", crosswind_mph, -40, 40)
    check_range("temperature_f", temperature_f, 20, 110)
    check_range("altitude_ft", altitude_ft, 0, 10000)
    check_range("elevation_change_ft", elevation_change_ft, -150, 150)


# ---------- HW4 tools ----------

def ball_flight_metrics(ball_speed_mph, launch_angle_deg, backspin_rpm, headwind_mph=0.0,
                        crosswind_mph=0.0, temperature_f=70.0, altitude_ft=0.0):
    check_range("ball_speed_mph", ball_speed_mph, 40, 200)
    check_range("launch_angle_deg", launch_angle_deg, 0, 45)
    check_range("backspin_rpm", backspin_rpm, 500, 12000)
    check_conditions(headwind_mph, crosswind_mph, temperature_f, altitude_ft)
    rho = air_density(temperature_f, altitude_ft)
    result = flight(ball_speed_mph, launch_angle_deg, backspin_rpm, rho, headwind_mph, crosswind_mph)
    return {**{k: round(float(v), 1) for k, v in result.items()},
            "air_density_kg_m3": round(rho, 3), "scope": PHYSICS_SCOPE}


def calibrated_ball_speed(club, stock_carry_yd):
    """Ball speed (mph) that gives this stock carry with the club's tour launch and spin."""
    _, launch, spin, _ = TOUR[club]
    gap = lambda v: flight(v, launch, spin, RHO_STOCK)["carry_yd"] - stock_carry_yd
    return brentq(gap, 40, 220, xtol=0.01)


def plays_like_metrics(club, stock_carry_yd, headwind_mph=0.0, crosswind_mph=0.0,
                       elevation_change_ft=0.0, temperature_f=70.0, altitude_ft=0.0):
    key = club_key(club)
    check_range("stock_carry_yd", stock_carry_yd, 50, 350)
    check_conditions(headwind_mph, crosswind_mph, temperature_f, altitude_ft, elevation_change_ft)
    speed = calibrated_ball_speed(key, stock_carry_yd)
    _, launch, spin, _ = TOUR[key]
    now = flight(speed, launch, spin, air_density(temperature_f, altitude_ft),
                 headwind_mph, crosswind_mph, elevation_change_ft)
    return {
        "club": key,
        "calibrated_ball_speed_mph": round(float(speed), 1),
        "carry_in_conditions_yd": round(float(now["carry_yd"]), 1),
        "change_vs_stock_yd": round(float(now["carry_yd"] - stock_carry_yd), 1),
        "lateral_drift_yd": round(float(now["lateral_drift_yd"]), 1),
        "scope": f"tour-average {key} launch {launch} deg and spin {spin} rpm; stock = sea level, 70 F, calm",
    }


def parse_bag(bag_rows):
    """Bag rows → [(club key, stock carry yd)]; rejects unknown clubs instead of skipping them."""
    bag = []
    for club, carry in bag_rows:
        key = club_key(club)
        check_range(f"stock carry for {key}", carry, 50, 350)
        bag.append((key, float(carry)))
    if not bag:
        raise ValueError("bag must contain at least one club")
    return bag


def recommend_club_metrics(target_distance_yd, bag_rows=None, headwind_mph=0.0, crosswind_mph=0.0,
                           elevation_change_ft=0.0, temperature_f=70.0, altitude_ft=0.0):
    check_range("target_distance_yd", target_distance_yd, 30, 350)
    check_conditions(headwind_mph, crosswind_mph, temperature_f, altitude_ft, elevation_change_ft)
    conditions = dict(headwind_mph=headwind_mph, crosswind_mph=crosswind_mph,
                      elevation_change_ft=elevation_change_ft, temperature_f=temperature_f,
                      altitude_ft=altitude_ft)
    checked = []
    for club, stock in parse_bag(DEFAULT_BAG if bag_rows is None else bag_rows):
        if not 0.7 * target_distance_yd <= stock <= 1.5 * target_distance_yd:
            continue  # clearly too short or too long; skip the physics
        try:
            carry = plays_like_metrics(club, stock, **conditions)["carry_in_conditions_yd"]
        except ValueError:
            continue
        checked.append((club, stock, carry))
    if not checked:
        raise ValueError("No club in the bag is within reach of this target in these conditions.")
    reaching = [c for c in checked if c[2] >= target_distance_yd]
    club, stock, carry = min(reaching, key=lambda c: c[2]) if reaching else max(checked, key=lambda c: c[2])
    return {
        "recommended_club": club,
        "recommended_stock_carry_yd": stock,
        "carry_in_conditions_yd": carry,
        "margin_yd": round(carry - target_distance_yd, 1),
        "plays_like_yd": round(target_distance_yd * stock / carry, 1),
        "clubs_checked": {c: y for c, _, y in sorted(checked, key=lambda c: c[2])},
        "scope": "shortest bag club that carries the target; tour-average launch and spin per club",
    }


def score_differential_metrics(adjusted_gross_score, course_rating, slope_rating, pcc=0.0):
    check_range("adjusted_gross_score", adjusted_gross_score, 50, 160)
    check_range("course_rating", course_rating, 55, 85)
    check_range("slope_rating", slope_rating, 55, 155)
    check_range("pcc", pcc, -1, 3)
    diff = (113 / slope_rating) * (adjusted_gross_score - course_rating - pcc)
    return {"score_differential": round(diff, 1),
            "scope": "WHS 18-hole formula; score assumed already adjusted to net double bogey"}


def round_half_up(x):
    return math.floor(x + 0.5)


def course_handicap_metrics(handicap_index, slope_rating, course_rating, par, allowance_pct=100.0):
    check_range("handicap_index", handicap_index, -10, 54)
    check_range("slope_rating", slope_rating, 55, 155)
    check_range("course_rating", course_rating, 55, 85)
    check_range("par", par, 60, 76)
    check_range("allowance_pct", allowance_pct, 50, 100)
    raw = handicap_index * slope_rating / 113 + (course_rating - par)
    course_hcp = round_half_up(raw)
    playing_hcp = round_half_up(course_hcp * allowance_pct / 100)
    return {"course_handicap_unrounded": round(raw, 2), "course_handicap_strokes": course_hcp,
            "playing_handicap_strokes": playing_hcp, "net_par_gross_score": par + playing_hcp,
            "scope": "WHS 18-hole formula; allowance 95% is typical for individual stroke play"}


# ---------- New in HW5 ----------

def shot_dispersion_metrics(club, stock_carry_yd, target_carry_yd=0.0, ball_speed_sd_pct=3.0,
                            launch_sd_deg=1.5, spin_sd_pct=10.0, n_shots=300, seed=0,
                            headwind_mph=0.0, crosswind_mph=0.0, elevation_change_ft=0.0,
                            temperature_f=70.0, altitude_ft=0.0):
    """Monte Carlo spread of carry when strike quality varies from shot to shot."""
    key = club_key(club)
    check_range("stock_carry_yd", stock_carry_yd, 50, 350)
    check_range("target_carry_yd", target_carry_yd, 0, 350)
    check_range("ball_speed_sd_pct", ball_speed_sd_pct, 0, 10)
    check_range("launch_sd_deg", launch_sd_deg, 0, 5)
    check_range("spin_sd_pct", spin_sd_pct, 0, 30)
    check_range("n_shots", n_shots, 50, 1000)
    check_range("seed", seed, 0, 2**31 - 1)
    check_conditions(headwind_mph, crosswind_mph, temperature_f, altitude_ft, elevation_change_ft)

    speed = calibrated_ball_speed(key, stock_carry_yd)
    _, launch, spin, _ = TOUR[key]
    rng = np.random.default_rng(int(seed))
    n = int(n_shots)
    speeds = speed * (1 + rng.normal(0, ball_speed_sd_pct / 100, n))
    launches = np.clip(launch + rng.normal(0, launch_sd_deg, n), 1, 45)
    spins = np.clip(spin * (1 + rng.normal(0, spin_sd_pct / 100, n)), 500, 12000)
    rho = air_density(temperature_f, altitude_ft)
    carries = np.array([flight(v, la, sp, rho, headwind_mph, crosswind_mph, elevation_change_ft,
                               max_step=0.05)["carry_yd"] for v, la, sp in zip(speeds, launches, spins)])
    p10, p50, p90 = np.percentile(carries, [10, 50, 90])
    result = {
        "club": key,
        "n_shots": n,
        "carry_mean_yd": round(float(carries.mean()), 1),
        "carry_sd_yd": round(float(carries.std(ddof=1)), 1),
        "carry_p10_yd": round(float(p10), 1),
        "carry_p50_yd": round(float(p50), 1),
        "carry_p90_yd": round(float(p90), 1),
        "prob_carry_at_least_target": None,
        "scope": ("normal strike spread on ball speed, launch and spin around tour-average launch and spin; "
                  "spread sizes are user assumptions, not measured; no side spin, so no left/right misses. "
                  + PHYSICS_SCOPE),
    }
    if target_carry_yd > 0:
        result["prob_carry_at_least_target"] = round(float((carries >= target_carry_yd).mean()), 3)
    return result


# WHS Rule 5.2a: number of lowest differentials used and adjustment, by record size.
WHS_TABLE = {3: (1, -2.0), 4: (1, -1.0), 5: (1, 0.0), 6: (2, -1.0), 7: (2, 0.0), 8: (2, 0.0),
             9: (3, 0.0), 10: (3, 0.0), 11: (3, 0.0), 12: (4, 0.0), 13: (4, 0.0), 14: (4, 0.0),
             15: (5, 0.0), 16: (5, 0.0), 17: (6, 0.0), 18: (6, 0.0), 19: (7, 0.0), 20: (8, 0.0)}


def handicap_index_metrics(score_differentials):
    """Handicap Index from a scoring record (oldest first), using the most recent 20 rounds."""
    if not isinstance(score_differentials, (list, tuple)) or len(score_differentials) < 3:
        raise ValueError("score_differentials needs at least 3 rounds (WHS minimum)")
    for i, d in enumerate(score_differentials):
        check_range(f"score_differentials[{i}]", d, -10, 70)
    recent = list(score_differentials)[-20:]
    n_used, adjustment = WHS_TABLE[len(recent)]
    used = sorted(recent)[:n_used]
    raw = sum(used) / n_used + adjustment
    index = min(math.floor(raw * 10 + 0.5 + 1e-9) / 10, 54.0)
    return {
        "handicap_index": index,
        "rounds_in_record": len(score_differentials),
        "rounds_considered": len(recent),
        "differentials_used": used,
        "adjustment": adjustment,
        "scope": ("WHS Rules 5.2a/5.2b: average of the lowest differentials from the most recent 20, "
                  "rounded to 0.1, max 54.0; soft/hard caps and exceptional-score reductions not applied"),
    }
