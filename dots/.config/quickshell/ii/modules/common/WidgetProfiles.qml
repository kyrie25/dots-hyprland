pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    property var profiles: ({})
    readonly property bool visualizerEnabled: Quickshell.screens.some(screen => forMonitor(screen.name).widgets.visualizer.enable)

    function forItem(item) {
        while (item) {
            if (item.widgetOptions !== undefined) return item.widgetOptions;
            item = item.parent;
        }
        return Config.options.background;
    }

    function forMonitor(name) {
        if (!name || !Config.ready) return Config.options.background;
        if (!profiles[name]) {
            const profile = profileComponent.createObject(root, { monitorName: name });
            profiles[name] = profile;
        }
        return profiles[name].options;
    }

    function copySettings(source, target) {
        for (const key of Object.keys(target)) {
            if (key === "objectName" || source[key] === undefined || typeof source[key] === "function") continue;
            if (source[key] !== null && typeof source[key] === "object" && !Array.isArray(source[key])) {
                copySettings(source[key], target[key]);
            } else {
                target[key] = source[key];
            }
        }
    }

    Component {
        id: profileComponent
        FileView {
            id: file
            required property string monitorName
            property alias options: adapter
            property bool loaded: false
            path: `${Directories.shellConfig}/widgets-${encodeURIComponent(monitorName)}.json`
            watchChanges: true
            onFileChanged: reload()
            onLoaded: loaded = true
            onLoadFailed: error => {
                if (error !== FileViewError.FileNotFound) return;
                // Seed each new monitor from the existing shared configuration once.
                root.copySettings(Config.options.background.widgets, adapter.widgets);
                adapter.widgetsLocked = Config.options.background.widgetsLocked;
                loaded = true;
                writeAdapter();
            }
            onAdapterUpdated: if (loaded) writeTimer.restart()
            property Timer timer: Timer {
                id: writeTimer
                interval: Config.readWriteDelay
                onTriggered: file.writeAdapter()
            }
            JsonAdapter {
                id: adapter
                property bool widgetsLocked: false
                property WidgetSettings widgets: WidgetSettings {}
            }
        }
    }
}
