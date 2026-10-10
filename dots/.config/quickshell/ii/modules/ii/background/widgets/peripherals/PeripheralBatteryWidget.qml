import QtQuick
import QtQuick.Layouts
import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets
import qs.modules.ii.background.widgets

AbstractBackgroundWidget {
    id: root
    configEntryName: "peripheralBattery"
    implicitWidth: 340
    implicitHeight: content.implicitHeight + 40
    Component.onCompleted: PeripheralBatteries.users++
    Component.onDestruction: PeripheralBatteries.users--

    Rectangle {
        id: card
        anchors.fill: parent
        radius: Appearance.rounding.verylarge
        color: Appearance.colors.colPrimaryContainer
        StyledRectangularShadow { target: card; z: -1 }
    }

    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 20 }
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            MaterialSymbol {
                text: "battery_charging_full"
                iconSize: 24
                color: Appearance.colors.colPrimary
            }
            StyledText {
                Layout.fillWidth: true
                text: Translation.tr("Peripheral batteries")
                color: Appearance.colors.colOnPrimaryContainer
                font.pixelSize: Appearance.font.pixelSize.normal
                font.weight: Font.DemiBold
            }
        }

        Repeater {
            model: PeripheralBatteries.devices
            delegate: ColumnLayout {
                id: row
                required property var modelData
                readonly property bool known: modelData.percentage !== null
                readonly property color batteryColor: known && modelData.percentage <= 20
                    ? Appearance.colors.colError : Appearance.colors.colPrimary
                Layout.fillWidth: true
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    MaterialSymbol {
                        text: row.modelData.kind.includes("mouse") ? "mouse"
                            : row.modelData.kind.includes("keyboard") ? "keyboard"
                            : row.modelData.kind.includes("head") || row.modelData.kind.includes("audio") ? "headphones"
                            : row.modelData.kind.includes("game") ? "sports_esports" : "devices_other"
                        iconSize: 22
                        color: Appearance.colors.colOnPrimaryContainer
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        StyledText {
                            Layout.fillWidth: true
                            text: row.modelData.name
                            color: Appearance.colors.colOnPrimaryContainer
                            elide: Text.ElideRight
                            font.pixelSize: Appearance.font.pixelSize.small
                        }
                        StyledText {
                            text: row.modelData.source + (row.modelData.charging ? " / " + Translation.tr("Charging") : "")
                            color: Appearance.colors.colOnPrimaryContainer
                            opacity: 0.6
                            font.pixelSize: Appearance.font.pixelSize.smaller
                        }
                    }
                    StyledText {
                        text: row.known ? row.modelData.percentage + "%" : Translation.tr("Unknown")
                        color: row.known ? row.batteryColor : Appearance.colors.colOnPrimaryContainer
                        opacity: row.known ? 1 : 0.6
                        font.pixelSize: Appearance.font.pixelSize.normal
                        font.weight: Font.DemiBold
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 4
                    radius: 2
                    color: ColorUtils.transparentize(Appearance.colors.colOnPrimaryContainer, 0.88)
                    visible: row.known
                    Rectangle {
                        width: parent.width * (row.modelData.percentage ?? 0) / 100
                        height: parent.height
                        radius: 2
                        color: row.batteryColor
                    }
                }
            }
        }

        StyledText {
            Layout.fillWidth: true
            visible: PeripheralBatteries.devices.length === 0
            text: PeripheralBatteries.ready ? Translation.tr("No connected battery peripherals") : Translation.tr("Reading batteries...")
            wrapMode: Text.WordWrap
            color: Appearance.colors.colOnPrimaryContainer
            opacity: 0.6
            font.pixelSize: Appearance.font.pixelSize.small
        }
        StyledText {
            Layout.fillWidth: true
            visible: PeripheralBatteries.unavailable.length > 0
            text: Translation.tr("Unavailable") + ": " + PeripheralBatteries.unavailable.join(", ")
            wrapMode: Text.WordWrap
            color: Appearance.colors.colOnPrimaryContainer
            opacity: 0.6
            font.pixelSize: Appearance.font.pixelSize.smaller
        }
    }
}
