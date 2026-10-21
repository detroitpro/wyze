"""Lights, groups and the read-only device list, on top of wyze-sdk.

This is the whole surface wyzectl offers. Cameras, locks and other devices appear in
``list_devices`` (read-only) and nowhere else, on purpose.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from wyze_sdk.models.devices import DeviceModels

from wyzectl.session import Session

# Color bulbs Wyze reports as MeshLight that wyze-sdk 2.3.9 doesn't list; without this the SDK
# drops them from bulbs.list() and sends them non-mesh commands.
EXTRA_MESH_BULBS = ["HL_A19C2"]
for _model in EXTRA_MESH_BULBS:
    for _known in (DeviceModels.MESH_BULB, DeviceModels.BULB):
        if _model not in _known:
            _known.append(_model)

WHITE_TEMP = (2700, 6500)
MESH_TEMP = (1800, 6500)
HEX_COLOR = re.compile(r"^#?[0-9a-fA-F]{6}$")


class LightError(ValueError):
    """A request wyzectl refuses before calling Wyze."""


@dataclass
class Device:
    name: str
    type: str
    model: str
    mac: str
    online: bool | None


@dataclass
class Light:
    name: str
    mac: str
    model: str
    kind: str
    online: bool | None
    on: bool | None = None
    brightness: int | None = None
    color_temp: int | None = None
    color: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Group:
    name: str
    lights: list[str]


def kind_of(model: str) -> str:
    if model in DeviceModels.LIGHT_STRIP:
        return "strip"
    if model in DeviceModels.MESH_BULB:
        return "color"
    return "white"


def temp_range(model: str) -> tuple[int, int]:
    return MESH_TEMP if model in DeviceModels.MESH_BULB else WHITE_TEMP


def _model(device: Any) -> str:
    product = getattr(device, "product", None)
    return getattr(product, "model", None) or getattr(device, "product_model", "") or ""


def _light(bulb: Any) -> Light:
    model = _model(bulb)
    return Light(
        name=(bulb.nickname or "").strip(),
        mac=bulb.mac,
        model=model,
        kind=kind_of(model),
        online=getattr(bulb, "is_online", None),
    )


def _with_state(light: Light, info: Any) -> Light:
    if info is None:
        return light
    light.on = getattr(info, "is_on", None)
    light.brightness = getattr(info, "brightness", None)
    light.color_temp = getattr(info, "color_temp", None)
    if light.kind != "white":
        color = getattr(info, "color", None)
        light.color = color.upper() if isinstance(color, str) else None
    return light


class Lights:
    def __init__(self, session: Session):
        self.session = session

    def devices(self) -> list[Device]:
        found = self.session.call(lambda c: c.devices_list())
        return [
            Device(
                name=(d.nickname or "").strip(),
                type=str(getattr(d, "type", "") or ""),
                model=_model(d),
                mac=d.mac,
                online=getattr(d, "is_online", None),
            )
            for d in found
        ]

    def list(self, state: bool = True) -> list[Light]:
        lights = [_light(b) for b in self.session.call(lambda c: c.bulbs.list())]
        if state:
            for light in lights:
                self._refresh(light)
        return sorted(lights, key=lambda x: x.name.lower())

    def get(self, name: str) -> Light:
        light = self.resolve(name)
        return self._refresh(light)

    def resolve(self, name: str) -> Light:
        return resolve(name, self.list(state=False))

    def set(
        self,
        name: str,
        *,
        on: bool | None = None,
        brightness: int | None = None,
        color_temp: int | None = None,
        color: str | None = None,
    ) -> Light:
        light = self.resolve(name)
        self._apply(light, on=on, brightness=brightness, color_temp=color_temp, color=color)
        return self._refresh(light)

    def groups(self) -> list[Group]:
        data = self.session.call(lambda c: c._api_client().get_object_list()["data"])
        lights = {x.mac: x.name for x in self.list(state=False)}
        result = []
        for g in data.get("device_group_list") or []:
            members = [
                lights[mac]
                for item in g.get("device_list") or []
                if (mac := item.get("device_mac") or item.get("mac")) in lights
            ]
            if members:
                name = (g.get("group_name") or "").strip()
                result.append(Group(name=name, lights=sorted(members)))
        return sorted(result, key=lambda x: x.name.lower())

    def set_group(self, group: str, **changes: Any) -> list[Light]:
        groups = self.groups()
        target = resolve(group, groups)
        all_lights = self.list(state=False)
        members = [x for x in all_lights if x.name in target.lights]
        for light in members:
            self._apply(light, **changes)
        return [self._refresh(x) for x in members]

    def _refresh(self, light: Light) -> Light:
        info = self.session.call(lambda c: c.bulbs.info(device_mac=light.mac))
        return _with_state(light, info)

    def _apply(
        self,
        light: Light,
        *,
        on: bool | None = None,
        brightness: int | None = None,
        color_temp: int | None = None,
        color: str | None = None,
    ) -> None:
        validate(light, on=on, brightness=brightness, color_temp=color_temp, color=color)
        target = {"device_mac": light.mac, "device_model": light.model}
        changing = any(v is not None for v in (brightness, color_temp, color))
        if on is False:
            self.session.call(lambda c: c.bulbs.turn_off(**target))
            return
        if on or changing:
            self.session.call(lambda c: c.bulbs.turn_on(**target))
        if brightness is not None:
            self.session.call(lambda c: c.bulbs.set_brightness(**target, brightness=brightness))
        if color_temp is not None:
            self.session.call(lambda c: c.bulbs.set_color_temp(**target, color_temp=color_temp))
        if color is not None:
            hex_color = color.lstrip("#").upper()
            self.session.call(lambda c: c.bulbs.set_color(**target, color=hex_color))


def validate(
    light: Light,
    *,
    on: bool | None = None,
    brightness: int | None = None,
    color_temp: int | None = None,
    color: str | None = None,
) -> None:
    if on is False and any(v is not None for v in (brightness, color_temp, color)):
        raise LightError("turning a light off takes no brightness, temperature or color")
    if brightness is not None and not 1 <= brightness <= 100:
        raise LightError("brightness is 1-100")
    if color_temp is not None:
        low, high = temp_range(light.model)
        if not low <= color_temp <= high:
            raise LightError(f"{light.name}: color temperature is {low}-{high} K")
    if color is not None:
        if light.kind == "white":
            raise LightError(f"{light.name} is a white bulb; it has no color")
        if not HEX_COLOR.match(color):
            raise LightError("color is a hex RGB value like ff8800")
    if color is not None and color_temp is not None:
        raise LightError("set either a color or a color temperature, not both")


def resolve(name: str, items: list[Any]) -> Any:
    """Exact name (case-insensitive; case breaks a tie), then MAC, then a unique substring."""
    raw = name.strip()
    want = raw.lower()
    exact = [x for x in items if x.name.lower() == want]
    if len(exact) == 1:
        return exact[0]
    same_case = [x for x in exact if x.name == raw]
    if len(same_case) == 1:
        return same_case[0]
    by_mac = [x for x in items if getattr(x, "mac", "").lower() == want]
    if len(by_mac) == 1:
        return by_mac[0]
    partial = [x for x in items if want in x.name.lower()]
    if len(partial) == 1:
        return partial[0]
    if not partial and not exact:
        names = ", ".join(sorted(x.name for x in items)) or "none"
        raise LightError(f"no match for {name!r} (have: {names})")
    names = ", ".join(sorted(x.name for x in (exact or partial)))
    raise LightError(f"{name!r} matches more than one: {names}")
