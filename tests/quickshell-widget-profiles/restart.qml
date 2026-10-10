import QtQuick
import Quickshell
import qs.modules.common
ShellRoot {
    property var first
    property var second
    Timer {
        interval: 250; running: Config.ready
        onTriggered: {
            first = WidgetProfiles.forMonitor("HDMI-A-1")
            second = WidgetProfiles.forMonitor("eDP-1")
        }
    }
    Timer {
        interval: 900; running: Config.ready
        onTriggered: {
            if (first.widgets.clock.x !== 900 || first.widgets.clock.digital.font.size !== 88 || first.widgetsLocked || first.widgets.weather.sizeMode !== "1x1" || second.widgets.clock.x !== 321 || second.widgets.weather.enable || !second.widgetsLocked) throw Error("Restart failed")
            console.log("RESTART TEST PASS")
            Qt.quit()
        }
    }
}
