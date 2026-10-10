#!/usr/bin/env python3
"""Read peripheral batteries without changing device settings."""
import json
import math

import dbus


def percentage(value):
    if value is None:
        return None
    value = float(value)
    return round(value) if math.isfinite(value) and 0 <= value <= 100 else None


def device(identity, name, source, level=None, charging=False, kind=""):
    return dict(id=str(identity), name=str(name), source=source,
                percentage=percentage(level), charging=bool(charging), kind=str(kind))


def bluetooth_devices(bus):
    objects = bus.get_object("org.bluez", "/").GetManagedObjects(
        dbus_interface="org.freedesktop.DBus.ObjectManager", timeout=3)
    devices = []
    for path, interfaces in objects.items():
        info = interfaces.get("org.bluez.Device1", {})
        if not info.get("Connected", False):
            continue
        battery = interfaces.get("org.bluez.Battery1", {})
        devices.append(device(info.get("Address", path), info.get("Alias", "Bluetooth device"),
                              "Bluetooth", battery.get("Percentage"), kind=info.get("Icon", "")))
    return devices


def razer_devices():
    from openrazer.client import DeviceManager
    devices = []
    for entry in DeviceManager().devices:
        if entry.has("battery"):
            try:
                devices.append(device(entry.serial, entry.name, "Razer", entry.battery_level,
                                      entry.is_charging, entry.type))
            except Exception:
                # A receiver can remain enumerated while its peripheral is asleep.
                devices.append(device(entry.serial, entry.name, "Razer", kind=entry.type))
    return devices


def upower_devices(bus):
    paths = bus.get_object("org.freedesktop.UPower", "/org/freedesktop/UPower").EnumerateDevices(
        dbus_interface="org.freedesktop.UPower", timeout=3)
    devices = []
    for path in paths:
        info = bus.get_object("org.freedesktop.UPower", path).GetAll(
            "org.freedesktop.UPower.Device", dbus_interface="org.freedesktop.DBus.Properties", timeout=3)
        # UPower types 1-4 are AC, computer battery, UPS, and monitor.
        if int(info.get("Type", 0)) < 5 or not info.get("IsPresent", False):
            continue
        devices.append(device(info.get("Serial") or info.get("NativePath") or path,
                              info.get("Model") or "Peripheral", "UPower",
                              info.get("Percentage") if info.get("State", 0) else None,
                              info.get("State") == 1, {5: "mouse", 6: "keyboard", 8: "phone",
                                                      17: "headphones", 18: "headset"}.get(int(info["Type"]), "")))
    return devices


def merge_devices(groups):
    merged = {}
    for group in groups:
        for entry in group:
            # BlueZ addresses match UPower serials; prefer the specialized source.
            key = entry["id"].lower().replace(":", "").replace("-", "")
            if key in merged:
                current = merged[key]
                if current["percentage"] is None:
                    current["percentage"] = entry["percentage"]
                current["charging"] |= entry["charging"]
            else:
                merged[key] = entry.copy()
    return sorted(merged.values(), key=lambda entry: (entry["source"] != "Bluetooth", entry["name"].lower()))


def collect():
    groups, errors = [], []
    for source, reader in [("Bluetooth", lambda: bluetooth_devices(dbus.SystemBus())),
                           ("Razer", razer_devices),
                           ("UPower", lambda: upower_devices(dbus.SystemBus()))]:
        try:
            groups.append(reader())
        except Exception:
            errors.append(source)
    return dict(devices=merge_devices(groups), unavailable=errors)


if __name__ == "__main__":
    print(json.dumps(collect()))
