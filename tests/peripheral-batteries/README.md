# Peripheral batteries

Enable **Peripheral batteries** in Desktop Settings or the desktop right-click
Widgets menu. Settings and drag positions are saved independently per monitor.

The horizontal bar also shows device icons and battery values beside the system
resources, using the same circular progress and number styling. Hover for all
device names, battery percentages and charging states. Up to three devices are
shown in the bar (one on very narrow screens); a +N count represents the rest.
Unknown battery values appear as ?. This replaces the old separate Bluetooth
battery indicator, and shares the desktop widget's poller.

The widget polls every 30 seconds while at least one instance is enabled:

- BlueZ: connected Bluetooth devices, including devices with no battery report
  (shown as Unknown).
- OpenRazer: battery-capable devices enumerated by the running user daemon.
- UPower: present peripheral devices such as mice, keyboards, headsets, and phones.
  The laptop battery, AC supply, UPS, and monitors are excluded.

The reader uses the system Python and `python-dbus`. Razer support additionally
uses `python-openrazer` and `openrazer-daemon`; these are optional for other sources.
It only reads battery data and does not configure devices. A source failure is
shown in the card without discarding readings from other sources. Bluetooth and
UPower reports with the same address/serial are merged. Charging information is
available from OpenRazer and UPower; BlueZ Battery1 reports only percentage.
Availability and accuracy depend on device firmware and Linux driver support;
an enumerated Razer receiver can expose the driver's last reading while asleep.

Run from the repository root:

```sh
python3 -m unittest discover -s tests/peripheral-batteries -v
bash tests/quickshell-widget-profiles/run.sh
python3 dots/.config/quickshell/ii/scripts/peripherals/battery.py
```
