"""Golf analytics MCP server: five HW4 tools plus two new ones (shot dispersion, Handicap Index).

Run with MCP Inspector:  uv run mcp dev server.py
Run over stdio:          uv run server.py
"""

from typing import Annotated

from pydantic import BaseModel, Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import golf_tools as gt

mcp = MCPServer(
    "golf-analytics",
    instructions=(
        "Golf shot physics and World Handicap System calculators. Every number comes from a "
        "calculation; results include a 'scope' field listing the model's assumptions. Distances "
        "are carry only (no roll). Wind: headwind positive into the golfer; crosswind positive "
        "blows left to right."
    ),
)

# Shared input types: the schema carries units and valid ranges, so bad values fail before any math runs.
Headwind = Annotated[float, Field(ge=-40, le=40, description="Wind into the golfer's face, mph; negative = tailwind")]
Crosswind = Annotated[float, Field(ge=-40, le=40, description="Wind across the line, mph; positive blows left to right")]
Temperature = Annotated[float, Field(ge=20, le=110, description="Air temperature, °F")]
Altitude = Annotated[float, Field(ge=0, le=10000, description="Course altitude above sea level, ft")]
Elevation = Annotated[float, Field(ge=-150, le=150, description="Target height minus ball height, ft; positive = uphill")]
Club = Annotated[str, Field(description="driver, 3-wood, 5-wood, hybrid, 3-iron … 9-iron, pw ('7 iron', '7i' also accepted)")]
StockCarry = Annotated[float, Field(ge=50, le=350, description="Golfer's normal carry with this club at sea level, 70 °F, no wind, yd")]


def run(fn, **kwargs):
    """Call a calculation; turn its ValueError into a ToolError the client can read."""
    try:
        return fn(**kwargs)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


# ---------- Result models (structured output) ----------

class BallFlight(BaseModel):
    carry_yd: float
    lateral_drift_yd: float
    apex_yd: float
    hang_time_s: float
    landing_angle_deg: float
    air_density_kg_m3: float
    scope: str


class PlaysLike(BaseModel):
    club: str
    calibrated_ball_speed_mph: float
    carry_in_conditions_yd: float
    change_vs_stock_yd: float
    lateral_drift_yd: float
    scope: str


class ClubRecommendation(BaseModel):
    recommended_club: str
    recommended_stock_carry_yd: float
    carry_in_conditions_yd: float
    margin_yd: float = Field(description="Carry minus target; negative means no club reaches")
    plays_like_yd: float
    clubs_checked: dict[str, float] = Field(description="Club → carry in these conditions, yd")
    scope: str


class ScoreDifferential(BaseModel):
    score_differential: float
    scope: str


class CourseHandicap(BaseModel):
    course_handicap_unrounded: float
    course_handicap_strokes: int
    playing_handicap_strokes: int
    net_par_gross_score: int
    scope: str


class ShotDispersion(BaseModel):
    club: str
    n_shots: int
    carry_mean_yd: float
    carry_sd_yd: float
    carry_p10_yd: float
    carry_p50_yd: float
    carry_p90_yd: float
    prob_carry_at_least_target: float | None = Field(description="Share of simulated shots carrying the target; null if no target")
    scope: str


class HandicapIndex(BaseModel):
    handicap_index: float
    rounds_in_record: int
    rounds_considered: int
    differentials_used: list[float]
    adjustment: float
    scope: str


class BagClub(BaseModel):
    club: Club
    stock_carry_yd: StockCarry


# ---------- HW4 tools ----------

@mcp.tool()
def simulate_ball_flight(
    ball_speed_mph: Annotated[float, Field(ge=40, le=200, description="Ball speed off the face, mph")],
    launch_angle_deg: Annotated[float, Field(ge=0, le=45, description="Vertical launch angle, degrees")],
    backspin_rpm: Annotated[float, Field(ge=500, le=12000, description="Backspin, rpm")],
    headwind_mph: Headwind = 0.0,
    crosswind_mph: Crosswind = 0.0,
    temperature_f: Temperature = 70.0,
    altitude_ft: Altitude = 0.0,
) -> BallFlight:
    """Simulate a shot from launch-monitor numbers: carry, apex, hang time, landing angle and wind drift."""
    return BallFlight(**run(gt.ball_flight_metrics, ball_speed_mph=ball_speed_mph,
                            launch_angle_deg=launch_angle_deg, backspin_rpm=backspin_rpm,
                            headwind_mph=headwind_mph, crosswind_mph=crosswind_mph,
                            temperature_f=temperature_f, altitude_ft=altitude_ft))


@mcp.tool()
def plays_like_distance(
    club: Club,
    stock_carry_yd: StockCarry,
    headwind_mph: Headwind = 0.0,
    crosswind_mph: Crosswind = 0.0,
    elevation_change_ft: Elevation = 0.0,
    temperature_f: Temperature = 70.0,
    altitude_ft: Altitude = 0.0,
) -> PlaysLike:
    """How far one club carries in wind, slope, heat or altitude, compared with its normal carry."""
    return PlaysLike(**run(gt.plays_like_metrics, club=club, stock_carry_yd=stock_carry_yd,
                           headwind_mph=headwind_mph, crosswind_mph=crosswind_mph,
                           elevation_change_ft=elevation_change_ft, temperature_f=temperature_f,
                           altitude_ft=altitude_ft))


@mcp.tool()
def recommend_club(
    target_distance_yd: Annotated[float, Field(ge=30, le=350, description="Distance to the target, yd")],
    bag: Annotated[list[BagClub] | None, Field(description="Golfer's clubs and stock carries; omit to use the default bag")] = None,
    headwind_mph: Headwind = 0.0,
    crosswind_mph: Crosswind = 0.0,
    elevation_change_ft: Elevation = 0.0,
    temperature_f: Temperature = 70.0,
    altitude_ft: Altitude = 0.0,
) -> ClubRecommendation:
    """Pick the shortest club in the bag that still carries the target in these conditions."""
    rows = None if bag is None else [(b.club, b.stock_carry_yd) for b in bag]
    return ClubRecommendation(**run(gt.recommend_club_metrics, target_distance_yd=target_distance_yd,
                                    bag_rows=rows, headwind_mph=headwind_mph,
                                    crosswind_mph=crosswind_mph, elevation_change_ft=elevation_change_ft,
                                    temperature_f=temperature_f, altitude_ft=altitude_ft))


@mcp.tool()
def score_differential(
    adjusted_gross_score: Annotated[float, Field(ge=50, le=160, description="18-hole score after net double bogey adjustment, strokes")],
    course_rating: Annotated[float, Field(ge=55, le=85, description="Course Rating of the tees played, strokes")],
    slope_rating: Annotated[float, Field(ge=55, le=155, description="Slope Rating of the tees played")],
    pcc: Annotated[float, Field(ge=-1, le=3, description="Playing conditions calculation, strokes; usually 0")] = 0.0,
) -> ScoreDifferential:
    """World Handicap System score differential for one 18-hole round."""
    return ScoreDifferential(**run(gt.score_differential_metrics, adjusted_gross_score=adjusted_gross_score,
                                   course_rating=course_rating, slope_rating=slope_rating, pcc=pcc))


@mcp.tool()
def course_handicap(
    handicap_index: Annotated[float, Field(ge=-10, le=54, description="Golfer's Handicap Index")],
    slope_rating: Annotated[float, Field(ge=55, le=155, description="Slope Rating of the tees")],
    course_rating: Annotated[float, Field(ge=55, le=85, description="Course Rating of the tees, strokes")],
    par: Annotated[int, Field(ge=60, le=76, description="Par of the course")],
    allowance_pct: Annotated[float, Field(ge=50, le=100, description="Handicap allowance, %; 95 for individual stroke play")] = 100.0,
) -> CourseHandicap:
    """World Handicap System course and playing handicap for a set of tees."""
    return CourseHandicap(**run(gt.course_handicap_metrics, handicap_index=handicap_index,
                                slope_rating=slope_rating, course_rating=course_rating, par=par,
                                allowance_pct=allowance_pct))


# ---------- New tools ----------

@mcp.tool()
def shot_dispersion(
    club: Club,
    stock_carry_yd: StockCarry,
    target_carry_yd: Annotated[float, Field(ge=0, le=350, description="Carry needed (e.g. to clear water), yd; 0 = none")] = 0.0,
    ball_speed_sd_pct: Annotated[float, Field(ge=0, le=10, description="Shot-to-shot ball speed spread, % (1 standard deviation)")] = 3.0,
    launch_sd_deg: Annotated[float, Field(ge=0, le=5, description="Shot-to-shot launch spread, degrees (1 SD)")] = 1.5,
    spin_sd_pct: Annotated[float, Field(ge=0, le=30, description="Shot-to-shot spin spread, % (1 SD)")] = 10.0,
    n_shots: Annotated[int, Field(ge=50, le=1000, description="Number of simulated shots")] = 300,
    seed: Annotated[int, Field(ge=0, description="Random seed, for repeatable results")] = 0,
    headwind_mph: Headwind = 0.0,
    crosswind_mph: Crosswind = 0.0,
    elevation_change_ft: Elevation = 0.0,
    temperature_f: Temperature = 70.0,
    altitude_ft: Altitude = 0.0,
) -> ShotDispersion:
    """Monte Carlo spread of carry when strike quality varies, and the chance of carrying a target."""
    return ShotDispersion(**run(gt.shot_dispersion_metrics, club=club, stock_carry_yd=stock_carry_yd,
                                target_carry_yd=target_carry_yd, ball_speed_sd_pct=ball_speed_sd_pct,
                                launch_sd_deg=launch_sd_deg, spin_sd_pct=spin_sd_pct, n_shots=n_shots,
                                seed=seed, headwind_mph=headwind_mph, crosswind_mph=crosswind_mph,
                                elevation_change_ft=elevation_change_ft, temperature_f=temperature_f,
                                altitude_ft=altitude_ft))


@mcp.tool()
def handicap_index(
    score_differentials: Annotated[list[float], Field(min_length=3, description="Score differentials, oldest first; the most recent 20 are used")],
) -> HandicapIndex:
    """World Handicap System Handicap Index from a record of score differentials."""
    return HandicapIndex(**run(gt.handicap_index_metrics, score_differentials=score_differentials))


if __name__ == "__main__":
    mcp.run()
