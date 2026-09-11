import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import qs.modules.common.functions

ContentPage {
    forceWidth: true

    Process {
        id: randomWallProc
        property string status: ""
        property string scriptPath: `${Directories.scriptPath}/colors/random/random_konachan_wall.sh`
        command: ["bash", "-c", FileUtils.trimFileProtocol(randomWallProc.scriptPath)]
        stdout: SplitParser {
            onRead: data => {
                randomWallProc.status = data.trim();
            }
        }
    }

    component SmallLightDarkPreferenceButton: RippleButton {
        id: smallLightDarkPreferenceButton
        required property bool dark
        property color colText: toggled ? Appearance.colors.colOnPrimary : Appearance.colors.colOnLayer2
        padding: 5
        implicitHeight: Math.max(58, lightDarkButtonContent.implicitHeight + topPadding + bottomPadding)
        Layout.fillWidth: true
        toggled: Appearance.m3colors.darkmode === dark
        colBackground: Appearance.colors.colLayer2
        onClicked: {
            Quickshell.execDetached(["bash", "-c", `${Directories.wallpaperSwitchScriptPath} --mode ${dark ? "dark" : "light"} --noswitch`]);
        }
        contentItem: Item {
            ColumnLayout {
                id: lightDarkButtonContent
                anchors.centerIn: parent
                spacing: 0
                MaterialSymbol {
                    Layout.alignment: Qt.AlignHCenter
                    iconSize: 30
                    text: dark ? "dark_mode" : "light_mode"
                    color: smallLightDarkPreferenceButton.colText
                }
                StyledText {
                    Layout.alignment: Qt.AlignHCenter
                    text: dark ? Translation.tr("Dark") : Translation.tr("Light")
                    font.pixelSize: Appearance.font.pixelSize.smaller
                    color: smallLightDarkPreferenceButton.colText
                }
            }
        }
    }

    // Wallpaper selection
    ContentSection {
        icon: "format_paint"
        title: Translation.tr("Wallpaper & Colors")
        Layout.fillWidth: true

        GridLayout {
            id: wallpaperPreviewGrid
            Layout.fillWidth: true
            columns: width >= 540 ? 2 : 1
            columnSpacing: 8
            rowSpacing: 8

            Repeater {
                model: HyprlandData.monitors

                delegate: Rectangle {
                    required property var modelData
                    readonly property var monitorWallpaper: Wallpapers.wallpaperForMonitor(modelData.name)

                    Layout.fillWidth: true
                    Layout.preferredWidth: 280
                    Layout.preferredHeight: Math.max(150, width * 9 / 16)
                    radius: Appearance.rounding.normal
                    color: Appearance.colors.colLayer2
                    clip: true

                    StyledImage {
                        anchors.fill: parent
                        fillMode: Image.PreserveAspectCrop
                        source: parent.monitorWallpaper.thumbnailPath || parent.monitorWallpaper.path
                        cache: false
                    }

                    Rectangle {
                        anchors {
                            left: parent.left
                            right: parent.right
                            bottom: parent.bottom
                        }
                        height: monitorLabel.implicitHeight + 14
                        color: ColorUtils.transparentize(Appearance.colors.colLayer0, 0.18)

                        StyledText {
                            id: monitorLabel
                            anchors {
                                left: parent.left
                                right: parent.right
                                verticalCenter: parent.verticalCenter
                                margins: 8
                            }
                            text: modelData.name
                            font.pixelSize: Appearance.font.pixelSize.small
                            font.weight: Font.Medium
                            color: Appearance.colors.colOnLayer0
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        GridLayout {
            id: wallpaperActionGrid
            Layout.fillWidth: true
            columns: width >= 540 ? 2 : 1
            columnSpacing: 6
            rowSpacing: 6

            RippleButtonWithIcon {
                enabled: !randomWallProc.running
                visible: Config.options.policies.weeb === 1
                Layout.fillWidth: true
                buttonRadius: Appearance.rounding.small
                materialIcon: "ifl"
                mainText: randomWallProc.running ? Translation.tr("Be patient...") : Translation.tr("Random: Konachan")
                onClicked: {
                    randomWallProc.scriptPath = `${Directories.scriptPath}/colors/random/random_konachan_wall.sh`;
                    randomWallProc.running = true;
                }
                StyledToolTip {
                    text: Translation.tr("Random SFW Anime wallpaper from Konachan\nImage is saved to ~/Pictures/Wallpapers")
                }
            }

            RippleButtonWithIcon {
                enabled: !randomWallProc.running
                visible: Config.options.policies.weeb === 1
                Layout.fillWidth: true
                buttonRadius: Appearance.rounding.small
                materialIcon: "ifl"
                mainText: randomWallProc.running ? Translation.tr("Be patient...") : Translation.tr("Random: osu! seasonal")
                onClicked: {
                    randomWallProc.scriptPath = `${Directories.scriptPath}/colors/random/random_osu_wall.sh`;
                    randomWallProc.running = true;
                }
                StyledToolTip {
                    text: Translation.tr("Random osu! seasonal background\nImage is saved to ~/Pictures/Wallpapers")
                }
            }

            RippleButtonWithIcon {
                Layout.fillWidth: true
                materialIcon: "wallpaper"
                mainText: Translation.tr("Choose file")
                onClicked: Quickshell.execDetached(`${Directories.wallpaperSwitchScriptPath}`)

                StyledToolTip {
                    text: Translation.tr("Pick a wallpaper image on your system (Ctrl+Super+T)")
                }
            }

            RippleButtonWithIcon {
                Layout.fillWidth: true
                materialIcon: "animated_images"
                mainText: Translation.tr("Wallpaper Engine")
                onClicked: {
                    Quickshell.execDetached([
                        "qs", "-p", FileUtils.trimFileProtocol(Quickshell.shellPath("shell.qml")),
                        "ipc", "call", "wallpaperSelector", "openWallpaperEngine"
                    ]);
                }
                StyledToolTip {
                    text: Translation.tr("Choose a Wallpaper Engine project for all displays or one monitor")
                }
            }

            RowLayout {
                Layout.columnSpan: wallpaperActionGrid.columns
                Layout.fillWidth: true
                Layout.minimumHeight: 58
                uniformCellSizes: true

                SmallLightDarkPreferenceButton {
                    Layout.fillHeight: true
                    dark: false
                }

                SmallLightDarkPreferenceButton {
                    Layout.fillHeight: true
                    dark: true
                }
            }
        }

        ConfigSelectionArray {
            currentValue: Config.options.appearance.palette.type
            onSelected: newValue => {
                Config.options.appearance.palette.type = newValue;
                Quickshell.execDetached(["bash", "-c", `${Directories.wallpaperSwitchScriptPath} --noswitch`]);
            }
            options: [
                {
                    "value": "auto",
                    "displayName": Translation.tr("Auto")
                },
                {
                    "value": "scheme-content",
                    "displayName": Translation.tr("Content")
                },
                {
                    "value": "scheme-expressive",
                    "displayName": Translation.tr("Expressive")
                },
                {
                    "value": "scheme-fidelity",
                    "displayName": Translation.tr("Fidelity")
                },
                {
                    "value": "scheme-fruit-salad",
                    "displayName": Translation.tr("Fruit Salad")
                },
                {
                    "value": "scheme-monochrome",
                    "displayName": Translation.tr("Monochrome")
                },
                {
                    "value": "scheme-neutral",
                    "displayName": Translation.tr("Neutral")
                },
                {
                    "value": "scheme-rainbow",
                    "displayName": Translation.tr("Rainbow")
                },
                {
                    "value": "scheme-tonal-spot",
                    "displayName": Translation.tr("Tonal Spot")
                }
            ]
        }

        ConfigSwitch {
            buttonIcon: "ev_shadow"
            text: Translation.tr("Transparency")
            checked: Config.options.appearance.transparency.enable
            onCheckedChanged: {
                Config.options.appearance.transparency.enable = checked;
            }
        }
    }

    ContentSection {
        icon: "screenshot_monitor"
        title: Translation.tr("Bar & screen")

        ConfigRow {
            ContentSubsection {
                title: Translation.tr("Bar position")
                ConfigSelectionArray {
                    currentValue: (Config.options.bar.bottom ? 1 : 0) | (Config.options.bar.vertical ? 2 : 0)
                    onSelected: newValue => {
                        Config.options.bar.bottom = (newValue & 1) !== 0;
                        Config.options.bar.vertical = (newValue & 2) !== 0;
                    }
                    options: [
                        {
                            displayName: Translation.tr("Top"),
                            icon: "arrow_upward",
                            value: 0 // bottom: false, vertical: false
                        },
                        {
                            displayName: Translation.tr("Left"),
                            icon: "arrow_back",
                            value: 2 // bottom: false, vertical: true
                        },
                        {
                            displayName: Translation.tr("Bottom"),
                            icon: "arrow_downward",
                            value: 1 // bottom: true, vertical: false
                        },
                        {
                            displayName: Translation.tr("Right"),
                            icon: "arrow_forward",
                            value: 3 // bottom: true, vertical: true
                        }
                    ]
                }
            }
            ContentSubsection {
                title: Translation.tr("Bar style")

                ConfigSelectionArray {
                    currentValue: Config.options.bar.cornerStyle
                    onSelected: newValue => {
                        Config.options.bar.cornerStyle = newValue; // Update local copy
                    }
                    options: [
                        {
                            displayName: Translation.tr("Hug"),
                            icon: "line_curve",
                            value: 0
                        },
                        {
                            displayName: Translation.tr("Float"),
                            icon: "page_header",
                            value: 1
                        },
                        {
                            displayName: Translation.tr("Rect"),
                            icon: "toolbar",
                            value: 2
                        }
                    ]
                }
            }
        }

        ConfigRow {
            ContentSubsection {
                title: Translation.tr("Screen round corner")

                ConfigSelectionArray {
                    currentValue: Config.options.appearance.fakeScreenRounding
                    onSelected: newValue => {
                        Config.options.appearance.fakeScreenRounding = newValue;
                    }
                    options: [
                        {
                            displayName: Translation.tr("No"),
                            icon: "close",
                            value: 0
                        },
                        {
                            displayName: Translation.tr("Yes"),
                            icon: "check",
                            value: 1
                        },
                        {
                            displayName: Translation.tr("When not fullscreen"),
                            icon: "fullscreen_exit",
                            value: 2
                        }
                    ]
                }
            }
            
        }
    }

    NoticeBox {
        Layout.fillWidth: true
        text: Translation.tr('Not all options are available in this app. You should also check the config file by hitting the "Config file" button on the topleft corner or opening %1 manually.').arg(Directories.shellConfigPath)

        Item {
            Layout.fillWidth: true
        }
        RippleButtonWithIcon {
            id: copyPathButton
            property bool justCopied: false
            Layout.fillWidth: false
            buttonRadius: Appearance.rounding.small
            materialIcon: justCopied ? "check" : "content_copy"
            mainText: justCopied ? Translation.tr("Path copied") : Translation.tr("Copy path")
            onClicked: {
                copyPathButton.justCopied = true
                Quickshell.clipboardText = FileUtils.trimFileProtocol(`${Directories.config}/illogical-impulse/config.json`);
                revertTextTimer.restart();
            }
            colBackground: ColorUtils.transparentize(Appearance.colors.colPrimaryContainer)
            colBackgroundHover: Appearance.colors.colPrimaryContainerHover
            colRipple: Appearance.colors.colPrimaryContainerActive

            Timer {
                id: revertTextTimer
                interval: 1500
                onTriggered: {
                    copyPathButton.justCopied = false
                }
            }
        }
    }
}
