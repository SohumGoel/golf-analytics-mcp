"""Independent checks: run with `uv run pytest -q`."""

import math

import pytest

import golf_tools as gt


def test_vacuum_matches_projectile_formula():
    v, theta = 50 * gt.MPH, 30
    carry = gt.flight(50, theta, 3000, rho=0.0)["carry_yd"]
    assert math.isclose(carry, v**2 * math.sin(math.radians(2 * theta)) / gt.G / gt.YD, rel_tol=1e-4)


@pytest.mark.parametrize("club", ["3-wood", "hybrid", "4-iron", "6-iron", "8-iron", "pw"])
def test_held_out_trackman_clubs(club):
    speed, launch, spin, carry = gt.TOUR[club]
    model = gt.flight(speed, launch, spin, gt.RHO_STOCK)["carry_yd"]
    assert abs(model - carry) / carry < 0.07  # HW4: mean 2.2%, worst (pw) 6.6%


def test_usga_score_differential_example():
    assert gt.score_differential_metrics(93, 72.4, 131)["score_differential"] == 17.8


def test_course_handicap_by_hand():
    r = gt.course_handicap_metrics(13.1, 135, 73.4, 72, allowance_pct=95)
    assert r["course_handicap_strokes"] == 17 and r["playing_handicap_strokes"] == 16


def test_handicap_index_usga_examples():
    assert gt.handicap_index_metrics([15.3, 15.2, 16.6])["handicap_index"] == 13.2       # Rule 5.2a, 3 scores
    assert gt.handicap_index_metrics([16.3, 17.5, 20.1, 19.0, 18.2, 21.4])["handicap_index"] == 15.9  # 6 scores


def test_handicap_index_best_8_of_last_20():
    record = [30.0] * 5 + [float(d) for d in range(10, 30)]   # 25 rounds; last 20 are 10..29
    r = gt.handicap_index_metrics(record)
    assert r["rounds_considered"] == 20 and r["handicap_index"] == 13.5  # mean of 10..17


def test_dispersion_zero_spread_equals_plays_like():
    d = gt.shot_dispersion_metrics("7-iron", 160, ball_speed_sd_pct=0, launch_sd_deg=0, spin_sd_pct=0, n_shots=50)
    assert d["carry_sd_yd"] == 0 and abs(d["carry_mean_yd"] - 160) < 0.2


def test_dispersion_is_repeatable_with_seed():
    a = gt.shot_dispersion_metrics("driver", 290, target_carry_yd=280, n_shots=100, seed=7)
    b = gt.shot_dispersion_metrics("driver", 290, target_carry_yd=280, n_shots=100, seed=7)
    assert a == b


@pytest.mark.parametrize("call", [
    lambda: gt.plays_like_metrics("putter", 160),
    lambda: gt.ball_flight_metrics(250, 12, 2500),
    lambda: gt.handicap_index_metrics([15.0, 16.0]),
    lambda: gt.shot_dispersion_metrics("7-iron", 160, ball_speed_sd_pct=25),
])
def test_invalid_inputs_raise(call):
    with pytest.raises(ValueError):
        call()
