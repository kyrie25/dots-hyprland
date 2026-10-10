import QtQuick
import QtQuick.Layouts
import qs.modules.common
import qs.modules.common.widgets
import qs.services

MouseArea {
    id: root
    property bool compact: false
    readonly property var displayedDevices: PeripheralBatteries.devices.slice(0, compact ? 1 : 3)
    implicitWidth: PeripheralBatteries.devices.length > 0 ? row.implicitWidth + 8 : 0
    implicitHeight: Appearance.sizes.barHeight
    visible: implicitWidth > 0
    hoverEnabled: true
    acceptedButtons: Qt.NoButton
    Component.onCompleted: PeripheralBatteries.users++
    Component.onDestruction: PeripheralBatteries.users--

    function deviceIcon(device) {
        const kind = device.kind.toLowerCase();
        return kind.includes("mouse") ? "mouse" : kind.includes("keyboard") ? "keyboard"
            : kind.includes("head") || kind.includes("audio") ? "headphones"
            : kind.includes("game") ? "sports_esports" : "devices_other";
    }

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: 6
        Repeater {
            model: root.displayedDevices
            delegate: RowLayout {
                id: indicator
                required property var modelData
                readonly property bool known: modelData.percentage !== null
                readonly property bool low: known && modelData.percentage <= 20 && !modelData.charging
                spacing: 2
                ClippedFilledCircularProgress {
                    id: progress
                    Layout.alignment: Qt.AlignVCenter
                    implicitSize: 20
                    lineWidth: Appearance.rounding.unsharpen
                    value: indicator.known ? indicator.modelData.percentage / 100 : 0
                    colPrimary: indicator.low ? Appearance.colors.colError : Appearance.colors.colOnSecondaryContainer
                    accountForLightBleeding: !indicator.low
                    enableAnimation: false
                    MaterialSymbol {
                        anchors.centerIn: parent
                        text: indicator.modelData.charging ? "bolt" : root.deviceIcon(indicator.modelData)
                        iconSize: Appearance.font.pixelSize.normal
                        font.weight: Font.DemiBold
                        fill: 1
                        color: Appearance.colors.colOnSecondaryContainer
                    }
                }
                Item {
                    Layout.alignment: Qt.AlignVCenter
                    implicitWidth: percentageMetrics.width
                    implicitHeight: percentageText.implicitHeight
                    TextMetrics {
                        id: percentageMetrics
                        text: "100"
                        font.pixelSize: Appearance.font.pixelSize.small
                    }
                    StyledText {
                        id: percentageText
                        anchors.centerIn: parent
                        color: indicator.low ? Appearance.colors.colError : Appearance.colors.colOnLayer1
                        font.pixelSize: Appearance.font.pixelSize.small
                        text: indicator.known ? indicator.modelData.percentage : "?"
                    }
                }
            }
        }
        StyledText {
            visible: PeripheralBatteries.devices.length > root.displayedDevices.length
            text: "+" + (PeripheralBatteries.devices.length - root.displayedDevices.length)
            color: Appearance.colors.colOnLayer1
            font.pixelSize: Appearance.font.pixelSize.small
        }
    }

    StyledPopup {
        hoverTarget: root
        ColumnLayout {
            anchors.centerIn: parent
            spacing: 4
            StyledPopupHeaderRow {
                icon: "battery_charging_full"
                label: Translation.tr("Peripheral batteries")
            }
            Repeater {
                model: PeripheralBatteries.devices
                delegate: StyledPopupValueRow {
                    required property var modelData
                    icon: root.deviceIcon(modelData)
                    label: modelData.name + " (" + modelData.source + "):"
                    value: (modelData.percentage === null ? Translation.tr("Unknown") : modelData.percentage + "%")
                        + (modelData.charging ? " / " + Translation.tr("Charging") : "")
                }
            }
            StyledText {
                visible: PeripheralBatteries.unavailable.length > 0
                text: Translation.tr("Unavailable") + ": " + PeripheralBatteries.unavailable.join(", ")
                color: Appearance.colors.colOnSurfaceVariant
            }
        }
    }
}
