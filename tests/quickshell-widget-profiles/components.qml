import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.modules.common
import qs.services
import qs.modules.settings
import qs.modules.ii.background
import qs.modules.common.widgets
import qs.modules.ii.mediaControls
import qs.modules.ii.background.widgets.clock
ShellRoot {
    property var settingsPage
    function checkScope(item) {
        if (item.widgetOptions !== undefined && item.widgetOptions !== canvas.widgetOptions) throw Error("Nested scope failed")
        for (const child of item.children ?? []) checkScope(child)
    }
    Item {
        id: canvas
        width: 1920; height: 1080
        property var widgetOptions: WidgetProfiles.forMonitor("HDMI-A-1")
    }
    Timer {
        interval: 900; running: Config.ready
        onTriggered: {
            const base = Qt.resolvedUrl(".").toString() + "/"
            const paths = ["modules/settings/BackgroundConfig.qml", "modules/ii/background/Background.qml", "modules/common/widgets/WidgetsSubmenu.qml", "modules/ii/mediaControls/MediaControls.qml"]
            for (const path of paths) {
                const c = Qt.createComponent(base + path)
                if (c.status !== Component.Ready) throw Error(path + ": " + c.errorString())
            }
            settingsPage = Qt.createComponent(base + "modules/settings/BackgroundConfig.qml").createObject(canvas, {monitorName: "HDMI-A-1"})
            if (!settingsPage) throw Error("Settings creation failed")
            for (const style of ["CookieClock", "DigitalClock", "PixelClock"]) {
                const clock = Qt.createComponent(base + "modules/ii/background/widgets/clock/" + style + ".qml").createObject(canvas)
                if (!clock) throw Error("Clock creation failed")
                checkScope(clock)
            }
            const widgets = ["clock/ClockWidget", "weather/WeatherWidget", "calendar/CalendarWidget", "worldclock/WorldClockWidget", "images/CustomImage", "media/MediaWidget", "resources/ResourcesWidget", "notes/NotesWidget", "usercard/UserCardWidget", "images/ImageConverterWidget", "visualizer/VisualizerWidget"]
            for (const path of widgets) {
                const c = Qt.createComponent(base + "modules/ii/background/widgets/" + path + ".qml")
                if (c.status !== Component.Ready) throw Error(path + ": " + c.errorString())
                const obj = c.createObject(canvas, {screenWidth:1920, screenHeight:1080, scaledScreenWidth:1920, scaledScreenHeight:1080, wallpaperScale:1})
                if (!obj || obj.widgetOptions !== canvas.widgetOptions) throw Error("Widget scope failed: " + path)
            }
            const model = Qt.createComponent(base + "services/WorldClockModel.qml").createObject(canvas, { configEntry: canvas.widgetOptions.widgets.worldClock })
            model.setTimezone(0, "Asia/Ho_Chi_Minh")
            if (canvas.widgetOptions.widgets.worldClock.timezones[0] !== "Asia/Ho_Chi_Minh" || WidgetProfiles.forMonitor("eDP-1").widgets.worldClock.timezones[0] !== "Asia/Tokyo") throw Error("Timezone isolation failed")

        }
    }
    Timer {
        interval: 1700; running: Config.ready
        onTriggered: {
            const loader = settingsPage.contentData.find(item => typeof item.loadMonitor === "function")
            if (!loader || loader.item.widgetOptions !== canvas.widgetOptions || loader.Layout.preferredHeight <= 0) throw Error("Settings layout failed")
            const oldContent = loader.item
            settingsPage.monitorName = "eDP-1"
            if (loader.item === oldContent || loader.item.widgetOptions !== WidgetProfiles.forMonitor("eDP-1")) throw Error("Settings switching failed")
            console.log("COMPONENT TEST PASS")
        }
    }
    Timer { interval: 2200; running: Config.ready; onTriggered: Qt.quit() }
}
