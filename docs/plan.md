# Plan

## Why

The owner's lights are Wyze bulbs (white and color). We want agents to control them ("warm white
at 30% in the living room") without the Wyze app, and nothing else on the account. Wyze has no
public device API: its developer console only issues an API key for logging in. Community
libraries use the app's private API. The available MCP servers wrap a personal fork of an older
wyze-sdk and expose cameras and locks too, so we built a small tool on the main wyze-sdk that
exposes lights only.

## v0.1.0

- Session: env credentials, cached tokens (0600), refresh on code 2001, login fallback.
- Lights: list with state, get, on/off, brightness, color temperature, color; validation by model
  (white bulbs 2700-6500 K and no color; color bulbs and strips 1800-6500 K or hex color).
- Groups: read from the app's `device_group_list`, act on the lights in a group.
- Read-only device list.
- CLI and MCP server (stdio) over the same functions.

## Not verified yet

Built and tested against a fake client only. Before relying on these, confirm against a real
account:

1. **Group shape.** `device_group_list` entries are assumed to have `group_name` and a
   `device_list` of `{device_mac}`. If groups come back empty while the app shows rooms, this is
   the first suspect.
2. **State after a change.** `set` re-reads the light right after changing it; Wyze may report the
   old state for a moment.
3. **Light strips.** Color and temperature go through wyze-sdk's mesh path; check a strip really
   changes.

## Later

- Scenes (save and restore the state of a group).
- Effects on light strips (`set_effect` exists in wyze-sdk).
- A smoke test the owner can run read-only (`wyzectl --json lights`, redacted).
