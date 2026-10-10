pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io

Singleton {
    id: root
    property int users: 0
    property var devices: []
    property var unavailable: []
    property bool ready: false

    function refresh() {
        if (!reader.running) reader.running = true;
    }
    onUsersChanged: if (users > 0) refresh()

    Timer {
        interval: 30000
        running: root.users > 0
        repeat: true
        onTriggered: root.refresh()
    }
    Process {
        id: reader
        command: ["timeout", "12", "/usr/bin/python3", Quickshell.shellPath("scripts/peripherals/battery.py")]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const result = JSON.parse(text);
                    root.devices = result.devices;
                    root.unavailable = result.unavailable;
                } catch (error) {
                    root.devices = [];
                    root.unavailable = ["Battery reader"];
                }
                root.ready = true;
            }
        }
    }
}
