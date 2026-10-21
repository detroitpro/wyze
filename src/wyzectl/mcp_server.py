"""MCP server (stdio) exposing the same light controls as the CLI. No camera or lock tools."""

from __future__ import annotations

from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from wyzectl.lights import Lights
from wyzectl.session import Session

mcp = FastMCP("wyze")
_lights: Lights | None = None


def lights() -> Lights:
    global _lights
    if _lights is None:
        _lights = Lights(Session())
    return _lights


@mcp.tool()
def list_devices() -> list[dict]:
    """Every device on the Wyze account: name, type, model, online. Read-only."""
    return [asdict(d) for d in lights().devices()]


@mcp.tool()
def list_lights() -> list[dict]:
    """All Wyze lights with their state: on, brightness (1-100), color_temp (K), color (hex).

    kind is "white" (temperature 2700-6500 K only), "color" or "strip" (1800-6500 K, or a color).
    """
    return [x.to_dict() for x in lights().list()]


@mcp.tool()
def list_groups() -> list[dict]:
    """Rooms/groups from the Wyze app, with the lights in each."""
    return [asdict(g) for g in lights().groups()]


@mcp.tool()
def get_light(name: str) -> dict:
    """One light's current state. name: the light's name (exact, or a unique part of it)."""
    return lights().get(name).to_dict()


@mcp.tool()
def set_light(
    name: str,
    on: bool | None = None,
    brightness: int | None = None,
    color_temp: int | None = None,
    color: str | None = None,
) -> dict:
    """Change one light. Setting brightness, color_temp or color also turns it on.

    on: true/false. brightness: 1-100. color_temp: Kelvin (white bulbs 2700-6500, color bulbs
    and strips 1800-6500). color: hex like "ff8800" (color bulbs and strips only). Give either
    color or color_temp, not both. Returns the state after the change.
    """
    return (
        lights()
        .set(name, on=on, brightness=brightness, color_temp=color_temp, color=color)
        .to_dict()
    )


@mcp.tool()
def set_group(
    group: str,
    on: bool | None = None,
    brightness: int | None = None,
    color_temp: int | None = None,
    color: str | None = None,
) -> list[dict]:
    """Change every light in a Wyze room/group, same arguments as set_light."""
    return [
        x.to_dict()
        for x in lights().set_group(
            group, on=on, brightness=brightness, color_temp=color_temp, color=color
        )
    ]


def serve() -> None:
    mcp.run()
