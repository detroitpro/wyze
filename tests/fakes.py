"""A fake wyze-sdk Client. Names and MACs are made up; never put real account data here."""

from __future__ import annotations

from types import SimpleNamespace

from wyze_sdk.errors import WyzeApiError

EXPIRED = {"code": "2001", "msg": "AccessTokenError"}

ENV = {
    "WYZE_EMAIL": "test@example.com",
    "WYZE_PASSWORD": "not-a-password",
    "WYZE_KEY_ID": "key-id",
    "WYZE_API_KEY": "api-key",
}


def fake_session(client, tmp_path):
    """A Session whose every login or cache read yields ``client``."""
    from wyzectl.session import Credentials, Session

    return Session(
        lambda: Credentials.from_env(ENV),
        cache_path=tmp_path / "session.json",
        client_factory=lambda **_: client,
    )


def bulb(name, mac, model, online=True, on=False, brightness=50, color_temp=3000, color=None):
    return SimpleNamespace(
        nickname=name,
        mac=mac,
        product=SimpleNamespace(model=model),
        is_online=online,
        type="Light",
        state=SimpleNamespace(on=on, brightness=brightness, color_temp=color_temp, color=color),
    )


def default_bulbs():
    return [
        bulb("Living Room Lamp", "AAAA00000001", "WLPA19C", color="FF0000", on=True),
        bulb("Living Room Ceiling", "AAAA00000002", "HL_HWB2"),
        bulb("Office Strip", "AAAA00000003", "HL_LSL"),
    ]


class FakeBulbs:
    def __init__(self, client):
        self.client = client

    def list(self):
        self.client.check()
        return list(self.client.bulbs_data)

    def info(self, *, device_mac):
        self.client.check()
        for b in self.client.bulbs_data:
            if b.mac == device_mac:
                s = b.state
                return SimpleNamespace(
                    is_on=s.on, brightness=s.brightness, color_temp=s.color_temp, color=s.color
                )
        return None

    def _state(self, mac):
        return next(b for b in self.client.bulbs_data if b.mac == mac).state

    def turn_on(self, *, device_mac, device_model):
        self.client.check()
        self.client.calls.append(("on", device_mac))
        self._state(device_mac).on = True

    def turn_off(self, *, device_mac, device_model):
        self.client.check()
        self.client.calls.append(("off", device_mac))
        self._state(device_mac).on = False

    def set_brightness(self, *, device_mac, device_model, brightness):
        self.client.check()
        self.client.calls.append(("brightness", device_mac, brightness))
        self._state(device_mac).brightness = brightness

    def set_color_temp(self, *, device_mac, device_model, color_temp):
        self.client.check()
        self.client.calls.append(("color_temp", device_mac, color_temp))
        self._state(device_mac).color_temp = color_temp

    def set_color(self, *, device_mac, device_model, color):
        self.client.check()
        self.client.calls.append(("color", device_mac, color))
        self._state(device_mac).color = color


class FakeClient:
    """Stands in for wyze_sdk.Client. ``expired`` makes the next call fail with code 2001."""

    logins = 0

    def __init__(
        self,
        token=None,
        refresh_token=None,
        email=None,
        password=None,
        key_id=None,
        api_key=None,
        totp_key=None,
        bulbs=None,
        groups=None,
    ):
        if email is not None:
            FakeClient.logins += 1
            token, refresh_token = f"access-{FakeClient.logins}", f"refresh-{FakeClient.logins}"
        self._token = token
        self._refresh_token = refresh_token
        self.bulbs_data = default_bulbs() if bulbs is None else list(bulbs)
        self.groups_data = groups or []
        self.calls = []
        self.expired = False
        self.refresh_fails = False
        self.bulbs = FakeBulbs(self)

    def check(self):
        if self.expired:
            raise WyzeApiError("The access token has expired.", EXPIRED)

    def refresh_token(self):
        if self.refresh_fails:
            raise WyzeApiError("refresh failed", {"code": "2002"})
        self.expired = False
        self._token = self._token + "-r"

    def devices_list(self):
        self.check()
        return list(self.bulbs_data) + [
            SimpleNamespace(
                nickname="Front Door",
                mac="BBBB00000001",
                type="Camera",
                product=SimpleNamespace(model="HL_CAM4"),
                is_online=True,
            )
        ]

    def _api_client(self):
        client = self

        class Api:
            def get_object_list(self):
                client.check()
                return {"data": {"device_list": [], "device_group_list": client.groups_data}}

        return Api()
