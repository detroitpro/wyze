"""wyzectl: Wyze lights and plugs from the command line.

  wyzectl devices                         every device on the account (read-only)
  wyzectl lights                          lights with their current state
  wyzectl groups                          rooms/groups from the Wyze app (lights only)
  wyzectl light get NAME
  wyzectl light on NAME | off NAME
  wyzectl light set NAME [--brightness 1-100] [--temp KELVIN] [--color RRGGBB]
  wyzectl group on|off|set GROUP ...      same, for every light in a group
  wyzectl plugs                           plugs with on/off state
  wyzectl plug get|on|off NAME
  wyzectl session check | forget
  wyzectl mcp                             MCP server on stdio

Credentials come from WYZE_EMAIL, WYZE_PASSWORD, WYZE_KEY_ID, WYZE_API_KEY (and optional
WYZE_TOTP_KEY). The session is cached in $XDG_CACHE_HOME/wyzectl/session.json (WYZECTL_CACHE).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from wyze_sdk.errors import WyzeClientError

from wyzectl import __version__
from wyzectl.lights import LightError, Lights
from wyzectl.plugs import Plugs
from wyzectl.session import ConfigError, Session


def _change_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--brightness", type=int, metavar="1-100")
    p.add_argument("--temp", type=int, metavar="KELVIN", dest="color_temp")
    p.add_argument("--color", metavar="RRGGBB")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="wyzectl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--version", action="version", version=f"wyzectl {__version__}")
    ap.add_argument("--json", action="store_true", help="JSON output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices")
    lights = sub.add_parser("lights")
    lights.add_argument("--no-state", action="store_true", help="names only (fewer API calls)")
    sub.add_parser("groups")

    for noun in ("light", "group"):
        p = sub.add_parser(noun)
        verbs = p.add_subparsers(dest="verb", required=True)
        if noun == "light":
            verbs.add_parser("get").add_argument("name")
        for verb in ("on", "off"):
            verbs.add_parser(verb).add_argument("name")
        s = verbs.add_parser("set")
        s.add_argument("name")
        _change_args(s)

    sub.add_parser("plugs")
    plug = sub.add_parser("plug").add_subparsers(dest="verb", required=True)
    for verb in ("get", "on", "off"):
        plug.add_parser(verb).add_argument("name")

    session = sub.add_parser("session")
    session.add_argument("verb", choices=["check", "forget"])
    sub.add_parser("mcp")
    return ap


def _fmt_light(x: dict) -> str:
    if x.get("on") is None:
        state = "?"
    else:
        state = "on" if x["on"] else "off"
    parts = [f"{x['name']:<24}", f"{state:<4}"]
    if x.get("on"):
        if x.get("brightness") is not None:
            parts.append(f"{x['brightness']:>3}%")
        if x.get("color") and x.get("kind") != "white":
            parts.append(f"#{x['color']}")
        elif x.get("color_temp"):
            parts.append(f"{x['color_temp']}K")
    parts.append(f"[{x['kind']}{'' if x.get('online') is not False else ', offline'}]")
    return "  ".join(parts)


def _print(data: Any, as_json: bool, kind: str) -> None:
    if as_json:
        print(json.dumps(data, indent=2))
        return
    rows = data if isinstance(data, list) else [data]
    for x in rows:
        if kind == "light":
            print(_fmt_light(x))
        elif kind == "device":
            online = "" if x["online"] is not False else "  (offline)"
            print(f"{x['name']:<28}  {x['type']:<14}  {x['model']}{online}")
        elif kind == "group":
            print(f"{x['name']}: {', '.join(x['lights'])}")
        elif kind == "plug":
            state = "?" if x["on"] is None else ("on" if x["on"] else "off")
            where = "outdoor" if x["outdoor"] else "indoor"
            offline = ", offline" if x["online"] is False else ""
            print(f"{x['name']:<24}  {state:<4}  [{where}{offline}]")
        else:
            print(x)


def run(args: argparse.Namespace, lights: Lights, plugs: Plugs | None = None) -> None:
    plugs = plugs or Plugs(lights.session)
    changes = {k: getattr(args, k, None) for k in ("brightness", "color_temp", "color")}
    if args.cmd == "plugs":
        _print([x.to_dict() for x in plugs.list()], args.json, "plug")
    elif args.cmd == "plug":
        if args.verb == "get":
            result = plugs.get(args.name)
        else:
            result = plugs.set(args.name, on=args.verb == "on")
        _print(result.to_dict(), args.json, "plug")
    elif args.cmd == "devices":
        _print([asdict(d) for d in lights.devices()], args.json, "device")
    elif args.cmd == "lights":
        _print([x.to_dict() for x in lights.list(state=not args.no_state)], args.json, "light")
    elif args.cmd == "groups":
        _print([asdict(g) for g in lights.groups()], args.json, "group")
    elif args.cmd == "light":
        if args.verb == "get":
            result = lights.get(args.name)
        elif args.verb in ("on", "off"):
            result = lights.set(args.name, on=args.verb == "on")
        else:
            if not any(v is not None for v in changes.values()):
                raise LightError("set needs --brightness, --temp or --color")
            result = lights.set(args.name, **changes)
        _print(result.to_dict(), args.json, "light")
    elif args.cmd == "group":
        if args.verb in ("on", "off"):
            result = lights.set_group(args.name, on=args.verb == "on")
        else:
            if not any(v is not None for v in changes.values()):
                raise LightError("set needs --brightness, --temp or --color")
            result = lights.set_group(args.name, **changes)
        _print([x.to_dict() for x in result], args.json, "light")
    elif args.cmd == "session":
        if args.verb == "forget":
            lights.session.forget()
            print("session cache removed")
        else:
            count = len(lights.devices())
            print(f"session ok ({count} devices)")


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    if args.cmd == "mcp":
        from wyzectl.mcp_server import serve

        serve()
        return
    try:
        session = Session()
        run(args, Lights(session), Plugs(session))
    except (LightError, ConfigError) as e:
        print(f"wyzectl: {e}", file=sys.stderr)
        sys.exit(2)
    except WyzeClientError as e:
        print(f"wyzectl: Wyze API error: {str(e).splitlines()[0]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
