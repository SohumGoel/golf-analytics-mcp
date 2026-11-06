# MCP demo transcript

Server `golf-analytics` over stdio, 2026-11-06 16:04.

**Tools listed by the server:** `simulate_ball_flight`, `plays_like_distance`, `recommend_club`, `score_differential`, `course_handicap`, `shot_dispersion`, `handicap_index`

## Original tool (HW4): `plays_like_distance`

Request:
```json
{
  "club": "7-iron",
  "stock_carry_yd": 160,
  "altitude_ft": 5280,
  "temperature_f": 85
}
```

Response (is_error=False):
```
{
  "club": "7-iron",
  "calibrated_ball_speed_mph": 113.7,
  "carry_in_conditions_yd": 174.4,
  "change_vs_stock_yd": 14.4,
  "lateral_drift_yd": 0.0,
  "scope": "tour-average 7-iron launch 16.1 deg and spin 7124 rpm; stock = sea level, 70 F, calm"
}
```

## Original tool (HW4): `recommend_club`

Request:
```json
{
  "target_distance_yd": 165,
  "headwind_mph": 15,
  "elevation_change_ft": 20
}
```

Response (is_error=False):
```
{
  "recommended_club": "4-iron",
  "recommended_stock_carry_yd": 196.0,
  "carry_in_conditions_yd": 168.6,
  "margin_yd": 3.6,
  "plays_like_yd": 191.8,
  "clubs_checked": {
    "9-iron": 108.7,
    "8-iron": 120.0,
    "7-iron": 131.9,
    "6-iron": 144.5,
    "5-iron": 157.4,
    "4-iron": 168.6,
    "hybrid": 194.7,
    "5-wood": 207.1
  },
  "scope": "shortest bag club that carries the target; tour-average launch and spin per club"
}
```

## New tool 1: `shot_dispersion`

Request:
```json
{
  "club": "7-iron",
  "stock_carry_yd": 160,
  "target_carry_yd": 155,
  "seed": 0
}
```

Response (is_error=False):
```
{
  "club": "7-iron",
  "n_shots": 300,
  "carry_mean_yd": 159.4,
  "carry_sd_yd": 6.6,
  "carry_p10_yd": 151.3,
  "carry_p50_yd": 159.3,
  "carry_p90_yd": 167.6,
  "prob_carry_at_least_target": 0.733,
  "scope": "normal strike spread on ball speed, launch and spin around tour-average launch and spin; spread sizes are user assumptions, not measured; no side spin, so no left/right misses. point-mass ball, pure backspin, constant spin, uniform wind; carry only, no roll"
}
```

## New tool 2: `handicap_index`

Request:
```json
{
  "score_differentials": [
    16.4,
    14.8,
    18.9,
    13.2,
    15.5,
    17.0,
    14.1,
    19.6,
    15.9,
    16.2
  ]
}
```

Response (is_error=False):
```
{
  "handicap_index": 14.0,
  "rounds_in_record": 10,
  "rounds_considered": 10,
  "differentials_used": [
    13.2,
    14.1,
    14.8
  ],
  "adjustment": 0.0,
  "scope": "WHS Rules 5.2a/5.2b: average of the lowest differentials from the most recent 20, rounded to 0.1, max 54.0; soft/hard caps and exceptional-score reductions not applied"
}
```

## Invalid input (schema range): `plays_like_distance`

Request:
```json
{
  "club": "7-iron",
  "stock_carry_yd": 160,
  "headwind_mph": 60
}
```

Response (is_error=True):
```
Error executing tool plays_like_distance: 1 validation error for plays_like_distanceArguments
headwind_mph
  Input should be less than or equal to 40 [type=less_than_equal, input_value=60, input_type=int]
    For further information visit https://errors.pydantic.dev/2.14/v/less_than_equal
```

## Invalid input (server check): `handicap_index`

Request:
```json
{
  "score_differentials": [
    15.3,
    15.2,
    99
  ]
}
```

Response (is_error=True):
```
Error executing tool handicap_index: score_differentials[2] must be a number from -10 to 70; got 99.0
```
