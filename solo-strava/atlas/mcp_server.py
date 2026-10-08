"""Stdio MCP for private local agents. Install free Python MCP SDK first.

Requires `pip install -r requirements-mcp.txt`; then set environment variables
from the private `solo-strava/.env` and run `python atlas/mcp_server.py`.
Never expose stdio MCP through a public endpoint without an approved auth proxy.
"""
from mcp.server.fastmcp import FastMCP
from route_tools import list_route_workouts, get_workout_route

mcp = FastMCP("solo-strava-route-tools")
mcp.tool()(list_route_workouts)
mcp.tool()(get_workout_route)

if __name__ == "__main__":
    mcp.run(transport="stdio")