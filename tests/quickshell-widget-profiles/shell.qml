import QtQuick
import Quickshell
import qs.modules.common
ShellRoot {
    property var first
    property var second
    Timer {
        interval: 250
        running: Config.ready
        repeat: false
        onTriggered: {
            console.log("ready", Config.ready)
            first = WidgetProfiles.forMonitor("HDMI-A-1")
            second = WidgetProfiles.forMonitor("eDP-1")
        }
    }
    Timer {
        interval: 750
        running: Config.ready
        onTriggered: {
            if (first.widgets.clock.x !== 321 || second.widgets.clock.x !== 321 || first.widgets.clock.digital.font.size !== 73 || !first.widgetsLocked || first.widgets.worldClock.timezones[0] !== "Asia/Tokyo") throw Error("Migration failed")
            first.widgets.clock.x = 900
            first.widgets.weather.sizeMode = "1x1"
            first.widgets.clock.digital.font.size = 88
            first.widgetsLocked = false
            second.widgets.weather.enable = false
        }
    }
    Timer {
        interval: 1300
        running: Config.ready
        onTriggered: {
            console.log("values", first.widgets.clock.x, second.widgets.clock.x, second.widgets.weather.sizeMode, Config.options.background.widgets.clock.x)
            if (second.widgets.clock.x !== 321 || second.widgets.weather.sizeMode !== "1x2" || second.widgets.clock.digital.font.size !== 73 || !second.widgetsLocked || first.widgets.weather.enable !== true || Config.options.background.widgets.clock.x !== 321) throw Error("Isolation failed")
            console.log("PROFILE TEST PASS")
            Qt.quit()
        }
    }
}
