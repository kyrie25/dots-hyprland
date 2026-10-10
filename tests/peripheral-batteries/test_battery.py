import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

script = Path(__file__).resolve().parents[2] / "dots/.config/quickshell/ii/scripts/peripherals/battery.py"
spec = importlib.util.spec_from_file_location("battery", script)
battery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(battery)


class FakeBus:
    def __init__(self, objects=None, properties=None):
        self.objects = objects
        self.properties = properties or {}

    def get_object(self, service, path):
        self.path = path
        return self

    def GetManagedObjects(self, **kwargs):
        return self.objects

    def EnumerateDevices(self, **kwargs):
        return list(self.properties)

    def GetAll(self, *args, **kwargs):
        return self.properties[self.path]


class BatteryTests(unittest.TestCase):
    def test_connected_bluetooth_and_unknown_battery(self):
        rows = battery.bluetooth_devices(FakeBus({
            "/mouse": {"org.bluez.Device1": {"Alias": "Mouse", "Address": "AA:BB", "Connected": True},
                       "org.bluez.Battery1": {"Percentage": 0}},
            "/headset": {"org.bluez.Device1": {"Alias": "Headset", "Connected": True}},
            "/offline": {"org.bluez.Device1": {"Alias": "Offline", "Connected": False},
                         "org.bluez.Battery1": {"Percentage": 90}},
        }))
        self.assertEqual([row["name"] for row in rows], ["Mouse", "Headset"])
        self.assertEqual(rows[0]["percentage"], 0)
        self.assertIsNone(rows[1]["percentage"])

    def test_upower_excludes_computer_and_absent_devices(self):
        rows = battery.upower_devices(FakeBus(properties={
            "/laptop": {"Type": 2, "IsPresent": True, "Percentage": 99},
            "/mouse": {"Type": 5, "IsPresent": True, "State": 1, "Percentage": 20, "Model": "Mouse"},
            "/absent": {"Type": 6, "IsPresent": False},
            "/unknown": {"Type": 17, "IsPresent": True, "State": 0, "Percentage": 0},
        }))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["charging"])
        self.assertIsNone(rows[1]["percentage"])

    def test_duplicate_bluetooth_upower_merges_charging_and_missing_level(self):
        rows = battery.merge_devices([
            [battery.device("AA:BB:CC", "Mouse", "Bluetooth")],
            [battery.device("aa-bb-cc", "Mouse", "UPower", 30, True)],
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "Bluetooth")
        self.assertEqual(rows[0]["percentage"], 30)
        self.assertTrue(rows[0]["charging"])

    def test_source_failure_does_not_hide_other_devices(self):
        with patch.object(battery, "bluetooth_devices", side_effect=RuntimeError), \
             patch.object(battery, "razer_devices", return_value=[battery.device("serial", "Razer", "Razer", 43)]), \
             patch.object(battery, "upower_devices", return_value=[]):
            result = battery.collect()
        self.assertEqual(result["unavailable"], ["Bluetooth"])
        self.assertEqual(result["devices"][0]["percentage"], 43)

    def test_invalid_levels_remain_unknown(self):
        for value in (None, -1, 101, float("nan")):
            self.assertIsNone(battery.percentage(value))
        self.assertEqual(battery.percentage(99.5), 100)


if __name__ == "__main__":
    unittest.main()
