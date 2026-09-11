pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets
import "." as SettingsComponents

ContentSection {
    id: root

    icon: "animated_images"
    title: Translation.tr("Wallpaper Engine")

    readonly property list<var> behaviorActions: [
        { label: Translation.tr("Keep running"), value: "keep" },
        { label: Translation.tr("Mute"), value: "mute" },
        { label: Translation.tr("Pause"), value: "pause" },
        { label: Translation.tr("Stop"), value: "stop" }
    ]
    readonly property list<var> monitorOptions: HyprlandData.monitors.map(monitor => ({
        label: monitor.name,
        value: monitor.name
    }))
    property string selectedMonitor: HyprlandData.monitors[0]?.name ?? ""
    readonly property var selectedWallpaper: Wallpapers.wallpaperForMonitor(selectedMonitor)
    readonly property string selectedProjectPath: selectedWallpaper.path || ""
    property string projectTitle: ""
    property list<var> projectProperties: []

    function restartRenderer() {
        Wallpapers.scheduleWallpaperEngineRestart()
    }

    function isWallpaperEngine(entry) {
        return entry?.type === "wallpaper-engine"
    }

    function hasOverride(name) {
        return Object.prototype.hasOwnProperty.call(selectedWallpaper.properties || {}, name)
    }

    function propertyValue(definition) {
        return hasOverride(definition.name)
            ? selectedWallpaper.properties[definition.name]
            : definition.value
    }

    function workshopId(path) {
        const parts = String(path || "").replace(/\/+$/, "").split("/")
        return parts[parts.length - 1] || ""
    }

    function loadProjectProperties() {
        projectProperties = []
        projectTitle = ""
        if (!isWallpaperEngine(selectedWallpaper) || !selectedProjectPath)
            return
        if (propertyLoader.running && propertyLoader.requestedPath === selectedProjectPath)
            return
        propertyLoader.running = false
        propertyLoader.requestedPath = selectedProjectPath
        propertyLoader.exec(["python3", Directories.wallpaperEngineScriptPath, "properties", selectedProjectPath])
    }

    onSelectedProjectPathChanged: loadProjectProperties()
    Component.onCompleted: loadProjectProperties()

    component BehaviorSelector: RowLayout {
        id: behaviorSelector
        required property string label
        required property string currentValue
        signal selected(string value)

        Layout.fillWidth: true
        spacing: 10

        StyledText {
            Layout.fillWidth: true
            text: behaviorSelector.label
            color: Appearance.colors.colOnSecondaryContainer
        }

        StyledComboBox {
            Layout.fillWidth: false
            Layout.minimumWidth: 240
            Layout.preferredWidth: 300
            Layout.maximumWidth: 300
            buttonIcon: "tune"
            model: root.behaviorActions
            textRole: "label"
            currentIndex: {
                const index = model.findIndex(action => action.value === behaviorSelector.currentValue)
                return index >= 0 ? index : 0
            }
            onActivated: index => behaviorSelector.selected(model[index].value)
        }
    }

    ContentSubsection {
        title: Translation.tr("Playback")

        ConfigRow {
            uniform: true

            ConfigSwitch {
                buttonIcon: Config.options.background.wallpaperEngine.paused ? "play_arrow" : "pause"
                text: Config.options.background.wallpaperEngine.paused
                    ? Translation.tr("Resume wallpapers")
                    : Translation.tr("Pause wallpapers")
                checked: Config.options.background.wallpaperEngine.paused
                onCheckedChanged: {
                    if (checked !== Config.options.background.wallpaperEngine.paused)
                        Wallpapers.setWallpaperEnginePaused(checked)
                }
            }

            ConfigSwitch {
                buttonIcon: Config.options.background.wallpaperEngine.muted ? "volume_off" : "volume_up"
                text: Translation.tr("Mute wallpaper audio")
                checked: Config.options.background.wallpaperEngine.muted
                onCheckedChanged: {
                    if (checked === Config.options.background.wallpaperEngine.muted) return
                    Config.options.background.wallpaperEngine.muted = checked
                    root.restartRenderer()
                }
            }
        }

        StyledText {
            Layout.leftMargin: 8
            text: Translation.tr("Runtime state: %1").arg(Wallpapers.wallpaperEngineRuntimeState)
            color: Appearance.colors.colSubtext
        }
    }

    ContentSubsection {
        title: Translation.tr("Performance and input")

        ConfigRow {
            uniform: true

            ConfigSpinBox {
                icon: "speed"
                text: Translation.tr("FPS")
                value: Config.options.background.wallpaperEngine.fps
                from: 1
                to: 240
                stepSize: 1
                onValueChanged: {
                    if (value === Config.options.background.wallpaperEngine.fps) return
                    Config.options.background.wallpaperEngine.fps = value
                    root.restartRenderer()
                }
            }

            ConfigSpinBox {
                icon: "volume_up"
                text: Translation.tr("Volume")
                value: Config.options.background.wallpaperEngine.volume
                from: 0
                to: 100
                stepSize: 5
                enabled: !Config.options.background.wallpaperEngine.muted
                onValueChanged: {
                    if (value === Config.options.background.wallpaperEngine.volume) return
                    Config.options.background.wallpaperEngine.volume = value
                    root.restartRenderer()
                }
            }
        }

        ContentSubsection {
            title: Translation.tr("Anti-aliasing")

            ConfigSelectionArray {
                currentValue: Config.options.background.wallpaperEngine.antiAliasing
                options: [
                    { displayName: Translation.tr("Off"), value: 0 },
                    { displayName: "2x", value: 2 },
                    { displayName: "4x", value: 4 },
                    { displayName: "8x", value: 8 }
                ]
                onSelected: value => {
                    Config.options.background.wallpaperEngine.antiAliasing = value
                    root.restartRenderer()
                }
            }
        }

        ConfigRow {
            uniform: true

            ConfigSwitch {
                buttonIcon: "graphic_eq"
                text: Translation.tr("Audio processing")
                checked: Config.options.background.wallpaperEngine.audioProcessing
                onCheckedChanged: {
                    if (checked === Config.options.background.wallpaperEngine.audioProcessing) return
                    Config.options.background.wallpaperEngine.audioProcessing = checked
                    root.restartRenderer()
                }
            }

            ConfigSwitch {
                buttonIcon: "blur_on"
                text: Translation.tr("Particles")
                checked: Config.options.background.wallpaperEngine.particles
                onCheckedChanged: {
                    if (checked === Config.options.background.wallpaperEngine.particles) return
                    Config.options.background.wallpaperEngine.particles = checked
                    root.restartRenderer()
                }
            }
        }

        ConfigRow {
            uniform: true

            ConfigSwitch {
                buttonIcon: "mouse"
                text: Translation.tr("Mouse input")
                checked: Config.options.background.wallpaperEngine.mouseInput
                onCheckedChanged: {
                    if (checked === Config.options.background.wallpaperEngine.mouseInput) return
                    Config.options.background.wallpaperEngine.mouseInput = checked
                    root.restartRenderer()
                }
            }

            ConfigSwitch {
                buttonIcon: "view_in_ar"
                text: Translation.tr("Wallpaper parallax")
                checked: Config.options.background.wallpaperEngine.parallax
                onCheckedChanged: {
                    if (checked === Config.options.background.wallpaperEngine.parallax) return
                    Config.options.background.wallpaperEngine.parallax = checked
                    root.restartRenderer()
                }
            }
        }
    }

    ContentSubsection {
        title: Translation.tr("Automatic behavior")
        tooltip: Translation.tr("If several rules match, Stop takes priority, followed by Pause and Mute.")

        BehaviorSelector {
            label: Translation.tr("When an app is fullscreen")
            currentValue: Config.options.background.wallpaperEngine.behavior.fullscreen
            onSelected: value => Config.options.background.wallpaperEngine.behavior.fullscreen = value
        }

        BehaviorSelector {
            label: Translation.tr("When a workspace has a tiled app")
            currentValue: Config.options.background.wallpaperEngine.behavior.maximized
            onSelected: value => Config.options.background.wallpaperEngine.behavior.maximized = value
        }

        BehaviorSelector {
            label: Translation.tr("When another app plays audio")
            currentValue: Config.options.background.wallpaperEngine.behavior.audioPlaying
            onSelected: value => Config.options.background.wallpaperEngine.behavior.audioPlaying = value
        }

        ConfigSwitch {
            buttonIcon: "filter_center_focus"
            text: Translation.tr("Fullscreen rule only for the focused app")
            checked: Config.options.background.wallpaperEngine.behavior.fullscreenOnlyActive
            onCheckedChanged: {
                if (checked !== Config.options.background.wallpaperEngine.behavior.fullscreenOnlyActive)
                    Config.options.background.wallpaperEngine.behavior.fullscreenOnlyActive = checked
            }
        }
    }

    ContentSubsection {
        title: Translation.tr("Per-monitor layout")

        StyledComboBox {
            id: monitorSelector
            buttonIcon: "monitor"
            model: root.monitorOptions
            textRole: "label"
            currentIndex: {
                const index = model.findIndex(monitor => monitor.value === root.selectedMonitor)
                return index >= 0 ? index : 0
            }
            onActivated: index => root.selectedMonitor = model[index].value
        }

        Rectangle {
            visible: root.isWallpaperEngine(root.selectedWallpaper)
            Layout.fillWidth: true
            implicitHeight: monitorDetails.implicitHeight + 24
            radius: Appearance.rounding.normal
            color: Appearance.colors.colLayer1

            RowLayout {
                id: monitorDetails
                anchors.fill: parent
                anchors.margins: 12
                spacing: 16

                Rectangle {
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: 190
                    Layout.preferredHeight: 107
                    radius: Appearance.rounding.normal
                    color: Appearance.colors.colLayer2
                    clip: true

                    StyledImage {
                        anchors.fill: parent
                        source: root.selectedWallpaper.thumbnailPath || root.selectedWallpaper.path
                        fillMode: Image.PreserveAspectCrop
                        cache: false
                    }
                }

                ColumnLayout {
                    Layout.alignment: Qt.AlignTop
                    Layout.fillWidth: true
                    spacing: 4

                    StyledText {
                        Layout.fillWidth: true
                        text: root.projectTitle || Translation.tr("Wallpaper Engine project")
                        font.pixelSize: Appearance.font.pixelSize.large
                        color: Appearance.colors.colOnSecondaryContainer
                        wrapMode: Text.Wrap
                    }

                    StyledText {
                        text: Translation.tr("Workshop %1").arg(root.workshopId(root.selectedProjectPath))
                        color: Appearance.colors.colSubtext
                    }

                    ContentSubsection {
                        title: Translation.tr("Scaling")

                        ConfigSelectionArray {
                            currentValue: root.selectedWallpaper.scaling
                            options: [
                                { displayName: Translation.tr("Stretch"), value: "stretch" },
                                { displayName: Translation.tr("Fit"), value: "fit" },
                                { displayName: Translation.tr("Fill"), value: "fill" },
                                { displayName: Translation.tr("Default"), value: "default" }
                            ]
                            onSelected: value => Wallpapers.updateMonitorWallpaperSetting(root.selectedMonitor, "scaling", value)
                        }
                    }

                    ContentSubsection {
                        title: Translation.tr("Horizontal crop alignment")

                        ConfigSelectionArray {
                            currentValue: root.selectedWallpaper.alignX
                            options: [
                                { displayName: Translation.tr("Left"), value: "left" },
                                { displayName: Translation.tr("Center"), value: "center" },
                                { displayName: Translation.tr("Right"), value: "right" }
                            ]
                            onSelected: value => Wallpapers.updateMonitorWallpaperSetting(root.selectedMonitor, "alignX", value)
                        }
                    }

                    ContentSubsection {
                        title: Translation.tr("Vertical crop alignment")

                        ConfigSelectionArray {
                            currentValue: root.selectedWallpaper.alignY
                            options: [
                                { displayName: Translation.tr("Top"), value: "top" },
                                { displayName: Translation.tr("Center"), value: "center" },
                                { displayName: Translation.tr("Bottom"), value: "bottom" }
                            ]
                            onSelected: value => Wallpapers.updateMonitorWallpaperSetting(root.selectedMonitor, "alignY", value)
                        }
                    }
                }
            }
        }

        StyledText {
            visible: !root.isWallpaperEngine(root.selectedWallpaper)
            Layout.leftMargin: 8
            text: Translation.tr("This monitor is not using a Wallpaper Engine project.")
            color: Appearance.colors.colSubtext
        }
    }

    ContentSubsection {
        visible: root.isWallpaperEngine(root.selectedWallpaper)
        title: Translation.tr("Wallpaper properties")

        StyledText {
            visible: propertyLoader.running
            text: Translation.tr("Loading project controls...")
            color: Appearance.colors.colSubtext
        }

        StyledText {
            visible: !propertyLoader.running && root.projectProperties.length === 0
            text: Translation.tr("This wallpaper does not expose configurable properties.")
            color: Appearance.colors.colSubtext
        }

        Repeater {
            model: root.projectProperties

            delegate: SettingsComponents.WallpaperEnginePropertyControl {
                required property var modelData
                definition: modelData
                effectiveValue: root.propertyValue(modelData)
                overridden: root.hasOverride(modelData.name)
                onEdited: value => Wallpapers.updateWallpaperEngineProperty(root.selectedMonitor, modelData.name, value)
                onResetRequested: Wallpapers.resetWallpaperEngineProperty(root.selectedMonitor, modelData.name)
            }
        }

        RippleButtonWithIcon {
            visible: Object.keys(root.selectedWallpaper.properties || {}).length > 0
            Layout.fillWidth: true
            materialIcon: "restart_alt"
            mainText: Translation.tr("Reset all project properties")
            onClicked: Wallpapers.updateMonitorWallpaperSetting(root.selectedMonitor, "properties", ({}))
        }
    }

    Process {
        id: propertyLoader
        property string requestedPath: ""
        stdout: StdioCollector { id: propertyOutput }
        stderr: StdioCollector { id: propertyError }
        onExited: (exitCode, exitStatus) => {
            if (requestedPath !== root.selectedProjectPath) return
            if (exitCode !== 0) {
                console.warn("[Wallpaper Engine settings] Failed to read project properties:", propertyError.text.trim())
                return
            }
            try {
                const result = JSON.parse(propertyOutput.text)
                root.projectTitle = result.title || ""
                root.projectProperties = result.properties || []
            } catch (error) {
                console.warn("[Wallpaper Engine settings] Invalid property data:", error)
            }
        }
    }
}
