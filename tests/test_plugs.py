import pytest

from tests.fakes import FakeClient, fake_session
from wyzectl.lights import LightError
from wyzectl.plugs import Plugs


@pytest.fixture
def client():
    return FakeClient(token="t", refresh_token="r")


@pytest.fixture
def plugs(client, tmp_path):
    return Plugs(fake_session(client, tmp_path))


def test_list_with_state_and_outdoor_flag(plugs):
    by_name = {p.name: p for p in plugs.list()}
    assert by_name["Chair Light"].on is True
    assert by_name["Bedroom Lamp"].on is False
    assert by_name["Patio Socket 1"].outdoor is True
    assert by_name["Patio Socket 1"].online is False
    assert by_name["Chair Light"].outdoor is False


def test_on_and_off(plugs, client):
    assert plugs.set("bedroom", on=True).on is True
    assert plugs.set("Chair Light", on=False).on is False
    assert client.calls == [("plug_on", "CCCC00000002"), ("plug_off", "CCCC00000001")]


def test_unknown_plug_makes_no_call(plugs, client):
    with pytest.raises(LightError, match="no match"):
        plugs.set("garage", on=True)
    assert client.calls == []
