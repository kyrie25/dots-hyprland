pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Qt.labs.folderlistmodel
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import qs
import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets

Scope {
    id: root

    property int carouselExtraCount: 5

    function openCentered(shouldOpen) {
        if (!shouldOpen) {
            GlobalStates.desktopMenuOpen = false
            return
        }
        const focusedName = Hyprland.focusedMonitor?.name
        const screen = Quickshell.screens.find(candidate => candidate.name === focusedName) ?? Quickshell.screens[0]
        GlobalStates.desktopMenuScreen = screen
        GlobalStates.desktopMenuX = screen.width / 2
        GlobalStates.desktopMenuY = screen.height / 2
        GlobalStates.desktopMenuOpen = true
    }

    function displayPathFor(path) {
        if (!path)
            return path
        return /\.(mp4|webm|mkv|avi|mov)$/i.test(path) ? Config.options.background.thumbnailPath : path
    }

    FolderListModel {
        id: wallpaperFolder
        folder: {
            const wallPath = Config.options.background.wallpaperPath
            if (!wallPath || wallPath.length === 0)
                return ""
            const lastSlash = wallPath.lastIndexOf("/")
            return "file://" + wallPath.substring(0, lastSlash)
        }
        showDirs: false
        nameFilters: ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.avif"]
    }

    property var randomWallpapers: {
        const current = FileUtils.trimFileProtocol(Config.options.background.wallpaperPath)
        const candidates = []
        for (let i = 0; i < wallpaperFolder.count; i++) {
            const filePath = FileUtils.trimFileProtocol(wallpaperFolder.get(i, "filePath").toString())
            if (filePath !== current)
                candidates.push(filePath)
        }
        for (let i = candidates.length - 1; i > 0; i--) {
            const randomIndex = Math.floor(Math.random() * (i + 1))
            const value = candidates[i]
            candidates[i] = candidates[randomIndex]
            candidates[randomIndex] = value
        }
        return candidates.slice(0, carouselExtraCount)
    }

    property var carouselModel: {
        const current = FileUtils.trimFileProtocol(Config.options.background.wallpaperPath)
        const extras = randomWallpapers.map(path => root.displayPathFor(path))
        return current && current.length > 0 ? [root.displayPathFor(current), ...extras] : extras
    }

    Loader {
        active: GlobalStates.desktopMenuOpen && !GlobalStates.screenLocked

        sourceComponent: PanelWindow {
            id: menuWindow
            screen: GlobalStates.desktopMenuScreen ?? Quickshell.screens[0]
            color: "transparent"
            exclusionMode: ExclusionMode.Ignore
            exclusiveZone: 0
            WlrLayershell.namespace: "quickshell:desktopMenu"
            WlrLayershell.layer: WlrLayer.Overlay

            anchors {
                top: true
                bottom: true
                left: true
                right: true
            }

            property Component openSubmenuComponent: null
            property real submenuAnchorY: 0
            property real submenuWidth: 284

            function showSubmenu(component, row) {
                submenuCloseTimer.stop()
                submenuAnchorY = menuCard.y + row.mapToItem(menuCard, 0, 0).y
                openSubmenuComponent = component
            }

            Timer {
                id: submenuCloseTimer
                interval: 250
                onTriggered: menuWindow.openSubmenuComponent = null
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: GlobalStates.desktopMenuOpen = false
            }

            Rectangle {
                id: menuCard
                width: 348
                implicitHeight: menuColumn.implicitHeight + 16
                x: Math.min(Math.max(GlobalStates.desktopMenuX - width / 2, 8), menuWindow.width - width - 8)
                y: Math.min(Math.max(GlobalStates.desktopMenuY - implicitHeight / 2, 8), menuWindow.height - implicitHeight - 8)
                radius: Appearance.rounding.verylarge
                color: "transparent"
                scale: 0.85
                opacity: 0
                transformOrigin: Item.Center

                Component.onCompleted: {
                    scale = 1
                    opacity = 1
                }

                Behavior on scale {
                    animation: Appearance.animation.elementMoveEnter.numberAnimation.createObject(this)
                }
                Behavior on opacity {
                    animation: Appearance.animation.elementMoveFast.numberAnimation.createObject(this)
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.AllButtons
                }

                ColumnLayout {
                    id: menuColumn
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    Rectangle {
                        id: previewCard
                        Layout.fillWidth: true
                        implicitHeight: 160
                        radius: Appearance.rounding.verylarge
                        color: Appearance.colors.colLayer0
                        clip: true

                        StyledRectangularShadow {
                            target: previewCard
                            z: -1
                        }

                        Carousel {
                            anchors.fill: parent
                            anchors.margins: 10
                            model: root.carouselModel
                            onWallpaperSelected: path => {
                                Wallpapers.select(path, Appearance.m3colors.darkmode)
                                GlobalStates.desktopMenuOpen = false
                            }
                        }
                    }

                    Rectangle {
                        id: actionCard
                        Layout.fillWidth: true
                        implicitHeight: actionColumn.implicitHeight + 16
                        radius: Appearance.rounding.verylarge
                        color: Appearance.colors.colLayer0

                        StyledRectangularShadow {
                            target: actionCard
                            z: -1
                        }

                        ColumnLayout {
                            id: actionColumn
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 2

                            MenuRow {
                                id: wallpaperRow
                                iconName: "format_paint"
                                label: Translation.tr("Wallpaper & style")
                                showChevron: true
                                onTriggered: {
                                    GlobalStates.desktopMenuOpen = false
                                    GlobalStates.wallpaperSelectorOpen = true
                                }

                                Component {
                                    id: wallpaperSubmenu
                                    WallpaperSubmenu {}
                                }

                                HoverHandler {
                                    onHoveredChanged: {
                                        if (hovered)
                                            menuWindow.showSubmenu(wallpaperSubmenu, wallpaperRow)
                                        else
                                            submenuCloseTimer.restart()
                                    }
                                }
                            }

                            MenuRow {
                                id: widgetsRow
                                iconName: "widgets"
                                label: Translation.tr("Widgets")
                                showChevron: true
                                onTriggered: menuWindow.showSubmenu(widgetsSubmenu, widgetsRow)

                                Component {
                                    id: widgetsSubmenu
                                    WidgetsSubmenu {}
                                }

                                HoverHandler {
                                    onHoveredChanged: {
                                        if (hovered)
                                            menuWindow.showSubmenu(widgetsSubmenu, widgetsRow)
                                        else
                                            submenuCloseTimer.restart()
                                    }
                                }
                            }

                            MenuRow {
                                iconName: "stacks"
                                label: Translation.tr("DropShelf")
                                showChevron: true
                                badgeText: DropShelf.items.length > 0 ? String(DropShelf.items.length) : ""
                                onTriggered: {
                                    GlobalStates.desktopMenuOpen = false
                                    GlobalStates.dropShelfX = GlobalStates.desktopMenuX
                                    GlobalStates.dropShelfY = GlobalStates.desktopMenuY
                                    GlobalStates.dropShelfOpen = true
                                }
                            }

                            MenuRow {
                                iconName: "video_template"
                                label: Translation.tr("Live Wallpaper")
                                showChevron: true
                                onTriggered: {
                                    GlobalStates.desktopMenuOpen = false
                                    Wallpapers.openFallbackPicker(Appearance.m3colors.darkmode)
                                }
                            }

                            MenuRow {
                                iconName: "settings"
                                label: Translation.tr("Settings")
                                onTriggered: {
                                    GlobalStates.desktopMenuOpen = false
                                    Quickshell.execDetached(["qs", "-p", Quickshell.shellPath("settings.qml")])
                                }
                            }
                        }
                    }
                }
            }

            Loader {
                active: menuWindow.openSubmenuComponent !== null
                width: menuWindow.submenuWidth
                sourceComponent: menuWindow.openSubmenuComponent
                x: menuCard.x + menuCard.width + 8 + menuWindow.submenuWidth > menuWindow.width
                    ? menuCard.x - menuWindow.submenuWidth - 8
                    : menuCard.x + menuCard.width + 8
                y: Math.min(Math.max(menuWindow.submenuAnchorY, 8), menuWindow.height - (item?.implicitHeight ?? 0) - 8)
                scale: active ? 1 : 0.9
                opacity: active ? 1 : 0
                transformOrigin: Item.Center

                Behavior on scale {
                    animation: Appearance.animation.elementMoveEnter.numberAnimation.createObject(this)
                }
                Behavior on opacity {
                    animation: Appearance.animation.elementMoveFast.numberAnimation.createObject(this)
                }

                HoverHandler {
                    onHoveredChanged: {
                        if (hovered)
                            submenuCloseTimer.stop()
                        else
                            submenuCloseTimer.restart()
                    }
                }
            }

            component MenuRow: RippleButton {
                required property string iconName
                required property string label
                property bool showChevron: false
                property string badgeText: ""
                signal triggered()

                Layout.fillWidth: true
                implicitHeight: 42
                buttonRadius: Appearance.rounding.verylarge
                colBackground: "transparent"
                colBackgroundHover: Appearance.colors.colLayer2
                onClicked: triggered()

                contentItem: RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 12

                    MaterialSymbol {
                        text: iconName
                        iconSize: Appearance.font.pixelSize.larger
                        color: Appearance.colors.colOnLayer1
                    }
                    StyledText {
                        Layout.fillWidth: true
                        text: label
                        font.pixelSize: Appearance.font.pixelSize.normal
                        color: Appearance.colors.colOnLayer1
                    }
                    StyledText {
                        visible: badgeText.length > 0
                        text: badgeText
                        font.pixelSize: Appearance.font.pixelSize.small
                        color: Appearance.colors.colOnLayer1
                        opacity: 0.6
                    }
                    MaterialSymbol {
                        visible: showChevron
                        text: "chevron_right"
                        iconSize: Appearance.font.pixelSize.normal
                        color: Appearance.colors.colOnLayer1
                        opacity: 0.4
                    }
                }
            }
        }
    }

    IpcHandler {
        target: "desktopMenu"

        function toggle(): void {
            root.openCentered(!GlobalStates.desktopMenuOpen)
        }

        function open(): void {
            root.openCentered(true)
        }

        function close(): void {
            GlobalStates.desktopMenuOpen = false
        }
    }
}
