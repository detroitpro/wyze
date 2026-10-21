"""Plugs: list with state, and on/off. Nothing else (no timers, away mode or usage records)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from wyze_sdk.models.devices import DeviceModels

from wyzectl.lights import resolve
from wyzectl.session import Session


@dataclass
class Plug:
    name: str
    mac: str
    model: str
    outdoor: bool
    online: bool | None
    on: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _plug(device: Any) -> Plug:
    product = getattr(device, "product", None)
    model = getattr(product, "model", None) or ""
    return Plug(
        name=(device.nickname or "").strip(),
        mac=device.mac,
        model=model,
        outdoor=model in DeviceModels.OUTDOOR_PLUG,
        online=getattr(device, "is_online", None),
    )


class Plugs:
    def __init__(self, session: Session):
        self.session = session

    def list(self, state: bool = True) -> list[Plug]:
        plugs = [_plug(p) for p in self.session.call(lambda c: c.plugs.list())]
        if state:
            for plug in plugs:
                self._refresh(plug)
        return sorted(plugs, key=lambda x: x.name.lower())

    def resolve(self, name: str) -> Plug:
        return resolve(name, self.list(state=False))

    def get(self, name: str) -> Plug:
        return self._refresh(self.resolve(name))

    def set(self, name: str, on: bool) -> Plug:
        plug = self.resolve(name)
        target = {"device_mac": plug.mac, "device_model": plug.model}
        if on:
            self.session.call(lambda c: c.plugs.turn_on(**target))
        else:
            self.session.call(lambda c: c.plugs.turn_off(**target))
        return self._refresh(plug)

    def _refresh(self, plug: Plug) -> Plug:
        info = self.session.call(lambda c: c.plugs.info(device_mac=plug.mac))
        if info is not None:
            plug.on = getattr(info, "is_on", None)
        return plug
