import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import qs.services
import qs.modules.common.widgets

ContentPage {
    id: root
    forceWidth: true
    property string monitorName: Hyprland.focusedMonitor?.name ?? Quickshell.screens[0]?.name ?? ""
    onMonitorNameChanged: {
        if (content.status === Loader.Ready) content.loadMonitor();
    }

    ContentSection {
        icon: "monitor"
        title: Translation.tr("Widget monitor")
        ConfigSelectionArray {
            currentValue: root.monitorName
            options: Quickshell.screens.map(screen => ({ displayName: screen.name, value: screen.name, icon: "monitor" }))
            onSelected: newValue => root.monitorName = newValue
        }
    }

    Loader {
        id: content
        Layout.fillWidth: true
        Layout.preferredHeight: item?.contentHeight ?? 0
        // Recreate editors so bindings broken by user input do not carry across monitors.
        function loadMonitor() {
            setSource(Qt.resolvedUrl("BackgroundConfigContent.qml"), { monitorName: root.monitorName });
        }
        Component.onCompleted: loadMonitor()
    }
}
