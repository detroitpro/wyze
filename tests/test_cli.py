import json

import pytest

from tests.fakes import FakeClient, fake_session
from wyzectl import cli
from wyzectl.lights import LightError, Lights


@pytest.fixture
def lights(tmp_path):
    return Lights(fake_session(FakeClient(token="t", refresh_token="r"), tmp_path))


def run(lights, *argv):
    cli.run(cli.parser().parse_args(list(argv)), lights)


def test_lights_json(lights, capsys):
    run(lights, "--json", "lights")
    names = [x["name"] for x in json.loads(capsys.readouterr().out)]
    assert names == ["Living Room Ceiling", "Living Room Lamp", "Office Strip"]


def test_light_set_text_output(lights, capsys):
    run(lights, "light", "set", "office", "--brightness", "30", "--temp", "2200")
    out = capsys.readouterr().out
    assert "Office Strip" in out and "30%" in out and "2200K" in out


def test_set_without_changes_is_refused(lights):
    with pytest.raises(LightError):
        run(lights, "light", "set", "office")


def test_plug_on_text_output(lights, capsys):
    run(lights, "plug", "on", "bedroom")
    out = capsys.readouterr().out
    assert "Bedroom Lamp" in out and "on" in out and "indoor" in out


def test_no_camera_or_lock_commands():
    choices = cli.parser()._subparsers._group_actions[0].choices
    assert set(choices) == {
        "devices",
        "lights",
        "groups",
        "light",
        "group",
        "plugs",
        "plug",
        "session",
        "mcp",
    }
