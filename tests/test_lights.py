import pytest

from tests.fakes import FakeClient, fake_session
from wyzectl.lights import LightError, Lights

GROUPS = [
    {
        "group_name": "Living Room",
        "device_list": [
            {"device_mac": "AAAA00000001"},
            {"device_mac": "AAAA00000002"},
            {"device_mac": "BBBB00000001"},
        ],
    },
    {"group_name": "Cameras", "device_list": [{"device_mac": "BBBB00000001"}]},
]


@pytest.fixture
def client():
    return FakeClient(token="t", refresh_token="r", groups=GROUPS)


@pytest.fixture
def lights(client, tmp_path):
    return Lights(fake_session(client, tmp_path))


def test_list_includes_state_and_kind(lights):
    by_name = {x.name: x for x in lights.list()}
    assert by_name["Living Room Lamp"].kind == "color"
    assert by_name["Living Room Lamp"].on is True
    assert by_name["Living Room Lamp"].color == "FF0000"
    assert by_name["Living Room Ceiling"].kind == "white"
    assert by_name["Living Room Ceiling"].color is None
    assert by_name["Office Strip"].kind == "strip"


def test_devices_is_read_only_listing_including_cameras(lights):
    types = {d.name: d.type for d in lights.devices()}
    assert types["Front Door"] == "Camera"


def test_resolve_exact_then_unique_substring(lights):
    assert lights.resolve("living room lamp").name == "Living Room Lamp"
    assert lights.resolve("strip").name == "Office Strip"


def test_resolve_ambiguous_and_missing(lights):
    with pytest.raises(LightError, match="more than one"):
        lights.resolve("living room")
    with pytest.raises(LightError, match="no match"):
        lights.resolve("garage")


def test_set_brightness_turns_light_on_first(lights, client):
    result = lights.set("Office Strip", brightness=40)
    assert client.calls == [("on", "AAAA00000003"), ("brightness", "AAAA00000003", 40)]
    assert result.on is True and result.brightness == 40


def test_off_sends_only_off(lights, client):
    lights.set("Living Room Lamp", on=False)
    assert client.calls == [("off", "AAAA00000001")]


def test_color_is_normalized(lights, client):
    lights.set("Office Strip", color="#00ff88")
    assert ("color", "AAAA00000003", "00FF88") in client.calls


@pytest.mark.parametrize(
    "name,changes,message",
    [
        ("Living Room Ceiling", {"color": "ff0000"}, "white bulb"),
        ("Living Room Ceiling", {"color_temp": 2000}, "2700-6500"),
        ("Office Strip", {"color_temp": 1800}, None),
        ("Office Strip", {"brightness": 0}, "1-100"),
        ("Office Strip", {"color": "red"}, "hex"),
        ("Office Strip", {"color": "ff0000", "color_temp": 3000}, "not both"),
        ("Office Strip", {"on": False, "brightness": 20}, "off takes no"),
    ],
)
def test_validation_happens_before_any_call(lights, client, name, changes, message):
    if message is None:
        lights.set(name, **changes)
        return
    with pytest.raises(LightError, match=message):
        lights.set(name, **changes)
    assert client.calls == []


def test_groups_list_only_lights(lights):
    groups = lights.groups()
    assert [(g.name, g.lights) for g in groups] == [
        ("Living Room", ["Living Room Ceiling", "Living Room Lamp"])
    ]


def test_set_group_changes_every_light(lights, client):
    result = lights.set_group("living room", on=False)
    assert sorted(c[1] for c in client.calls) == ["AAAA00000001", "AAAA00000002"]
    assert all(x.on is False for x in result)
