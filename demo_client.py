"""Demo client: launches server.py as a subprocess over stdio, calls tools, saves demo_transcript.md.

Run: uv run demo_client.py
"""

import asyncio
import json
import sys
from datetime import datetime

from mcp import Client, StdioServerParameters

CALLS = [
    ("Original tool (HW4)", "plays_like_distance",
     {"club": "7-iron", "stock_carry_yd": 160, "altitude_ft": 5280, "temperature_f": 85}),
    ("Original tool (HW4)", "recommend_club",
     {"target_distance_yd": 165, "headwind_mph": 15, "elevation_change_ft": 20}),
    ("New tool 1", "shot_dispersion",
     {"club": "7-iron", "stock_carry_yd": 160, "target_carry_yd": 155, "seed": 0}),
    ("New tool 2", "handicap_index",
     {"score_differentials": [16.4, 14.8, 18.9, 13.2, 15.5, 17.0, 14.1, 19.6, 15.9, 16.2]}),
    ("Invalid input (schema range)", "plays_like_distance",
     {"club": "7-iron", "stock_carry_yd": 160, "headwind_mph": 60}),
    ("Invalid input (server check)", "handicap_index",
     {"score_differentials": [15.3, 15.2, 99]}),
]


async def main():
    server = StdioServerParameters(command=sys.executable, args=["server.py"])
    lines = [f"# MCP demo transcript\n\nServer `golf-analytics` over stdio, {datetime.now():%Y-%m-%d %H:%M}.\n"]
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
        lines.append("**Tools listed by the server:** " + ", ".join(f"`{t.name}`" for t in tools) + "\n")
        for label, name, args in CALLS:
            result = await client.call_tool(name, args)
            body = (json.dumps(result.structured_content, indent=2) if result.structured_content
                    else result.content[0].text)
            lines += [f"## {label}: `{name}`\n", f"Request:\n```json\n{json.dumps(args, indent=2)}\n```\n",
                      f"Response (is_error={result.is_error}):\n```\n{body}\n```\n"]
            print(f"{label}: {name} -> is_error={result.is_error}")
    with open("demo_transcript.md", "w") as f:
        f.write("\n".join(lines))
    print("Saved demo_transcript.md")


if __name__ == "__main__":
    asyncio.run(main())
