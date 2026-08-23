import QtQuick
import QtQuick.Layouts

import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets
import qs.modules.ii.background.widgets.weather as WeatherWidgets
import qs.modules.ii.mediaControls as MediaControls
import qs.services

Item {
    id: root

    property int edgeMargin: 34
    readonly property var activePlayer: MprisController.activePlayer
    readonly property bool hasPlayer: activePlayer !== null
        && ((activePlayer?.trackTitle?.length ?? 0) > 0 || (activePlayer?.trackArtist?.length ?? 0) > 0)
    readonly property var latestNotifications: Notifications.list.slice(Math.max(0, Notifications.list.length - 2)).reverse()
    property bool mediaExpanded: false

    anchors.fill: parent

    Item {
        id: weatherPanel
        anchors {
            top: parent.top
            left: parent.left
            topMargin: root.edgeMargin
            leftMargin: root.edgeMargin
        }
        width: 420
        height: 120
        visible: (Weather.data?.temp?.length ?? 0) > 0 && Weather.data.temp !== "0"
        opacity: visible ? 1 : 0

        Behavior on opacity {
            animation: Appearance.animation.elementMoveFast.numberAnimation.createObject(this)
        }

        StyledRectangularShadow {
            target: weatherBackground
        }

        Rectangle {
            id: weatherBackground
            anchors.fill: parent
            radius: Appearance.rounding?.verylarge ?? 30
            color: Appearance.colors.colPrimaryContainer

            WeatherWidgets.WeatherExpandedContent {}
        }
    }

    MediaControls.PlayerControl {
        id: activePlayerControl
        anchors {
            left: parent.left
            bottom: parent.bottom
            leftMargin: root.edgeMargin
            bottomMargin: 20
        }
        width: Appearance.sizes.mediaControlsWidth
        height: Appearance.sizes.mediaControlsHeight
        player: root.activePlayer
        radius: Appearance.rounding.large
        coverClickAction: () => root.mediaExpanded = !root.mediaExpanded
        visible: root.hasPlayer
        opacity: visible ? 1 : 0

        Behavior on opacity {
            animation: Appearance.animation.elementMoveFast.numberAnimation.createObject(this)
        }
    }

    Item {
        id: expandedMedia
        anchors {
            left: parent.left
            bottom: activePlayerControl.top
            leftMargin: root.edgeMargin
            bottomMargin: -Appearance.sizes.elevationMargin
        }
        width: Appearance.sizes.mediaControlsWidth
        height: playerStack.implicitHeight
        visible: root.mediaExpanded && root.hasPlayer
        opacity: visible ? 1 : 0

        Behavior on opacity {
            animation: Appearance.animation.elementMoveFast.numberAnimation.createObject(this)
        }

        Column {
            id: playerStack
            width: parent.width
            spacing: -Appearance.sizes.elevationMargin

            Repeater {
                model: MprisController.players.filter(player => player !== root.activePlayer)

                delegate: MediaControls.PlayerControl {
                    required property var modelData

                    width: playerStack.width
                    height: Appearance.sizes.mediaControlsHeight
                    player: modelData
                    radius: Appearance.rounding.large
                }
            }
        }
    }

    Column {
        id: notificationStack
        anchors {
            top: parent.top
            right: parent.right
            topMargin: root.edgeMargin
            rightMargin: root.edgeMargin
        }
        width: Math.min(300, Math.max(250, parent.width * 0.18))
        spacing: 8

        Repeater {
            model: root.latestNotifications

            delegate: Item {
                id: previewItem
                required property var modelData

                width: notificationStack.width
                height: 56

                Toolbar {
                    anchors.fill: parent
                    clip: true
                    padding: 8
                    spacing: 8

                    NotificationAppIcon {
                        Layout.alignment: Qt.AlignVCenter
                        appIcon: previewItem.modelData.appIcon
                        image: previewItem.modelData.image
                        summary: previewItem.modelData.summary
                        urgency: previewItem.modelData.urgency
                        implicitSize: 32
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.maximumWidth: notificationStack.width - 64
                        spacing: 1

                        StyledText {
                            Layout.fillWidth: true
                            text: previewItem.modelData.appName || Translation.tr("Notification")
                            font.pixelSize: Appearance.font.pixelSize.smaller
                            color: Appearance.colors.colSubtext
                            elide: Text.ElideRight
                        }
                        StyledText {
                            Layout.fillWidth: true
                            text: previewItem.modelData.summary || previewItem.modelData.body || Translation.tr("New notification")
                            font.pixelSize: Appearance.font.pixelSize.small
                            color: Appearance.colors.colOnSurfaceVariant
                            elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }

}
