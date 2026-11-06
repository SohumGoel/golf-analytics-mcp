# golf-analytics MCP server

An MCP server exposing seven golf calculators: the five analytical tools from my HW4 agent (ball flight, plays-like distance, club recommendation, WHS score differential, course handicap) and two new ones (shot dispersion, Handicap Index). Built with the official MCP Python SDK (`mcp` 2.3, `MCPServer`).

## Setup

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12+ is installed automatically). For MCP Inspector you also need Node.js.

```bash
cd golf-mcp
uv sync                      # install mcp, scipy, numpy, pytest
uv run pytest -q             # 17 independent checks
uv run mcp dev server.py     # open MCP Inspector in the browser
uv run demo_client.py        # scripted stdio client → demo_transcript.md
```

In MCP Inspector: **Connect → Tools → List Tools**, pick a tool, fill in the form, then **Run Tool**.

### Use from Claude Code or Claude Desktop

```bash
claude mcp add golf-analytics -- uv --directory /absolute/path/to/golf-mcp run server.py
```

For Claude Desktop, add this to `claude_desktop_config.json`:

```json
{ "mcpServers": { "golf-analytics": {
    "command": "uv", "args": ["--directory", "/absolute/path/to/golf-mcp", "run", "server.py"] } } }
```

## Tools

Shared conditions inputs: `headwind_mph` (−40 to 40, negative = tailwind), `crosswind_mph` (−40 to 40, positive = left-to-right), `temperature_f` (20–110), `altitude_ft` (0–10,000), and `elevation_change_ft` (−150 to 150) for the club tools. Physics assumptions: point-mass ball, pure backspin, constant spin, wind uniform with height, carry only (no roll); drag and lift constants fitted to TrackMan 2023 PGA Tour averages (held-out carry error 2.2%). "Stock" carry means sea level, 70 °F, no wind.

| Tool | Purpose | Typed inputs (units, valid range) | Structured result |
|---|---|---|---|
| `simulate_ball_flight` (HW4) | Shot from launch-monitor numbers | ball speed (mph, 40–200), launch (°, 0–45), backspin (rpm, 500–12,000), conditions | carry, apex, drift (yd); hang time (s); landing angle (°); air density; scope |
| `plays_like_distance` (HW4) | One club's carry in conditions | club, stock carry (yd, 50–350), conditions | carry in conditions, change from stock, drift (yd); calibrated ball speed; scope |
| `recommend_club` (HW4) | Shortest club that carries a target | target (yd, 30–350), optional bag `[{club, stock_carry_yd}]`, conditions | club, carry, margin, plays-like yardage, every club checked; scope |
| `score_differential` (HW4) | WHS differential for one round | score (50–160), Course Rating (55–85), Slope (55–155), PCC (−1 to 3) | differential; scope |
| `course_handicap` (HW4) | Strokes received on a set of tees | Index (−10 to 54), Slope, Course Rating, par (60–76), allowance (%, 50–100) | course and playing handicap (strokes), net-par score; scope |
| `shot_dispersion` (**new**) | Spread of carry when strike quality varies; chance of carrying a target | club, stock carry, target (yd, 0 = none), ball-speed spread (%, 0–10), launch spread (°, 0–5), spin spread (%, 0–30), shots (50–1,000), seed, conditions | mean, SD, P10/P50/P90 carry (yd); probability of carrying the target; scope |
| `handicap_index` (**new**) | Handicap Index from a scoring record | list of score differentials, oldest first (≥ 3 items, each −10 to 70) | index, rounds considered, differentials used, adjustment; scope |

## Invalid-input behavior

Invalid input never returns a number. The server answers with `isError: true` and a readable message, at one of two levels:

1. **Schema level.** Ranges and types are part of each tool's JSON schema, so the SDK rejects bad values before any calculation runs, e.g. `headwind_mph: 60` → "Input should be less than or equal to 40".
2. **Calculation level.** Checks the schema can't express, such as an unknown club (`putter`) or a differential of 99, raise `ToolError` with the reason.

## Files

- `golf_tools.py`: pure calculations (no MCP code)
- `server.py`: MCP tool wrappers, input schemas, result models
- `test_tools.py`: independent checks (projectile formula, held-out TrackMan clubs, USGA worked examples)
- `demo_client.py`: stdio client that records `demo_transcript.md`

## Sources

TrackMan (2024), *Introducing updated tour averages* (2023 PGA Tour data). USGA, *Rules of Handicapping* Rule 5.2 and WHS FAQs. Smits & Smith (1994), golf ball aerodynamics. MCP Python SDK documentation.
