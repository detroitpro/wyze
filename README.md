# wyzectl

Control Wyze lights from the command line, or from an AI agent over MCP.

`wyzectl` covers **lights only**: Wyze bulbs (white and color) and light strips, plus the rooms
and groups you set up in the Wyze app. It can also list every device on the account, read-only.
There are no camera, lock or other device controls, on purpose.

It is a thin layer over [wyze-sdk](https://github.com/shauntarves/wyze-sdk), which talks to the
same cloud API the Wyze app uses. That API is not publicly documented, so Wyze can change it at
any time; when it does, this tool breaks until wyze-sdk catches up.

## Install

```bash
uv tool install git+https://github.com/heka-vault/wyze@v0.1.0
```

Python 3.12-3.14.

## Credentials

Create an API key at the [Wyze Developer API Console](https://developer-api-console.wyze.com/)
([Wyze's instructions](https://support.wyze.com/hc/en-us/articles/16129834216731-Creating-an-API-Key)),
then set:

| Variable | What |
|---|---|
| `WYZE_EMAIL`, `WYZE_PASSWORD` | Your Wyze account login |
| `WYZE_KEY_ID`, `WYZE_API_KEY` | From the developer console (one key per account, valid one year) |
| `WYZE_TOTP_KEY` | Optional: the authenticator-app secret, if your account uses TOTP two-factor |

Wyze rate-limits logins, so `wyzectl` caches the session (access and refresh tokens) in
`$XDG_CACHE_HOME/wyzectl/session.json` (mode `600`; override with `WYZECTL_CACHE`). It refreshes
an expired token and logs in again only when the refresh token has expired too. Treat that file
like a password: it controls your Wyze account.

## Use

```bash
wyzectl devices                                   # everything on the account (read-only)
wyzectl lights                                    # every light with on/off, brightness, color
wyzectl groups                                    # rooms/groups from the Wyze app
wyzectl light on "Desk Lamp"
wyzectl light set desk --brightness 40 --temp 2700
wyzectl light set "Office Strip" --color ff8800
wyzectl group off "Living Room"
wyzectl --json lights
wyzectl session check                             # is the login working?
```

Names match exactly (case-insensitive) first, then by a unique part of the name. Setting
brightness, temperature or color also turns the light on. Ranges: brightness 1-100; white bulbs
2700-6500 K; color bulbs and strips 1800-6500 K or a hex color.

## MCP

`wyzectl mcp` runs an MCP server on stdio with tools `list_devices`, `list_lights`, `list_groups`,
`get_light`, `set_light` and `set_group`. Example client config:

```json
{
  "mcpServers": {
    "wyze": { "command": "wyzectl", "args": ["mcp"] }
  }
}
```

The server needs the same environment variables. Agents can change your lights with it; that's
the point, and it's also why nothing else is exposed.

## Develop

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Tests run against a fake client; they never touch a real account.

## License

MIT
