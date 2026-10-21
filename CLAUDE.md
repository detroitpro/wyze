# wyze: agent operating manual

`wyzectl` controls Wyze lights and plugs from the command line and over MCP. It is a thin layer over
[wyze-sdk](https://github.com/shauntarves/wyze-sdk), which reverse-engineers the cloud API the
Wyze app uses. heka uses it so its agents can turn lights on and off, dim them and change their
color, and switch plugs.

This repository is **public**. Everything in it, including issues, PRs, commit messages and test
fixtures, is read by strangers.

Read [docs/plan.md](docs/plan.md) before non-trivial work.

## Layout

| Path | What |
|---|---|
| `src/wyzectl/session.py` | Credentials from the environment, the cached session (0600 file), refresh on expiry (code 2001), login fallback |
| `src/wyzectl/lights.py` | Device list (read-only), lights, groups, validation, name matching |
| `src/wyzectl/plugs.py` | Plugs: list with state, on/off |
| `src/wyzectl/cli.py` | argparse CLI over `lights.py` |
| `src/wyzectl/mcp_server.py` | FastMCP server (stdio) over the same functions |
| `tests/fakes.py` | Fake wyze-sdk client. Made-up names and MACs only |

## Commands

```bash
uv sync
uv run pytest                                    # the PR gate, with:
uv run ruff check . && uv run ruff format --check .
uv run wyzectl --help
```

## Rules

- **Lights and plugs only.** wyzectl changes lights (bulbs, strips, groups of them) and turns
  plugs on and off, nothing else. Cameras, locks, thermostats, vacuums and sensors show up in
  `devices` and nowhere else. Don't add controls for them without an issue that says so and the
  owner's agreement; a camera or lock control is a security decision, not a feature.
- **You have no Wyze account, and you don't need one.** Everything is built and tested against
  `tests/fakes.py`. Anything that needs a real account (checking a payload shape, a new device
  model) is a request to the owner: say exactly which read-only `wyzectl` commands to run, and
  ask for the output with names and MACs redacted.
- **Never log, print or commit a credential or token.** That includes the session cache, API
  key, key ID, password, TOTP secret, and raw auth responses. `Credentials.__repr__` hides values;
  keep it that way.
- **No real account data in the repo.** Fixtures, docs, issues and PRs use made-up names and MACs
  (`AAAA00000001`, `test@example.com`).
- **Validate before calling Wyze.** Ranges and model rules live in `lights.validate`; a refused
  request must make no API call (tests assert this).
- **Pin wyze-sdk exactly** (`==` in `pyproject.toml`). Bump it in its own PR after reading its
  changes.
- **Every change comes with a test** against the fake client.

## Workflow

Work happens in GitHub issues and pull requests on `detroitpro/wyze`. One issue per bug or
feature; the PR closes it. CI (`.github/workflows/ci.yml`) must be green before merge. Releases
are tags `vX.Y.Z` with the version bumped in `pyproject.toml` and `src/wyzectl/__init__.py`.
