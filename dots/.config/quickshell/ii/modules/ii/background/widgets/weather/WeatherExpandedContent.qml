import QtQuick
import QtQuick.Layouts

import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets

ColumnLayout {
    anchors {
        fill: parent
        margins: 14
    }
    spacing: 8

    RowLayout {
        Layout.fillWidth: true
        spacing: 12

        StyledText {
            Layout.alignment: Qt.AlignTop
            text: Weather.data?.temp ?? "--°"
            font {
                pixelSize: 40
                weight: Font.Bold
            }
            color: Appearance.colors.colPrimary
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: -2

            StyledText {
                text: Weather.data?.description ?? ""
                font.pixelSize: Appearance.font.pixelSize.normal
                font.weight: Font.DemiBold
                color: Appearance.colors.colOnPrimaryContainer
                elide: Text.ElideRight
            }
            StyledText {
                text: Weather.data?.city ?? "--"
                font.pixelSize: Appearance.font.pixelSize.small
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
                elide: Text.ElideRight
            }
        }

        Item { Layout.fillWidth: true }

        MaterialShapeWrappedMaterialSymbol {
            Layout.topMargin: -5
            Layout.alignment: Qt.AlignVCenter
            shape: MaterialShape.Shape.Cookie12Sided
            color: Appearance.colors.colPrimary
            colSymbol: Appearance.colors.colOnPrimary
            text: Icons.getWeatherIcon(Weather.data.wCode) ?? "cloud"
            iconSize: 24
            fill: 1
            padding: 10
            implicitWidth: 50
            implicitHeight: 50
        }
    }

    Item { Layout.fillHeight: true }

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 5
        spacing: 16

        RowLayout {
            spacing: 2
            MaterialSymbol {
                iconSize: Appearance.font.pixelSize.smaller
                text: "humidity_mid"
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
            }
            StyledText {
                text: Weather.data?.humidity ?? "--"
                font.pixelSize: Appearance.font.pixelSize.smaller
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
            }
        }

        RowLayout {
            spacing: 2
            MaterialSymbol {
                iconSize: Appearance.font.pixelSize.smaller
                text: "rainy"
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
            }
            StyledText {
                text: Weather.data?.cr ?? "--"
                font.pixelSize: Appearance.font.pixelSize.smaller
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
            }
        }

        RowLayout {
            spacing: 2
            MaterialSymbol {
                iconSize: Appearance.font.pixelSize.smaller
                text: "air"
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
            }
            StyledText {
                text: Weather.data?.wind ?? "--"
                font.pixelSize: Appearance.font.pixelSize.smaller
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
            }
        }

        RowLayout {
            spacing: 2
            MaterialSymbol {
                iconSize: Appearance.font.pixelSize.smaller
                text: "visibility"
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
            }
            StyledText {
                text: Weather.data?.visib ?? "--"
                font.pixelSize: Appearance.font.pixelSize.smaller
                color: Appearance.colors.colOnPrimaryContainer
                opacity: 0.6
            }
        }

        Item { Layout.fillWidth: true }

        ColumnLayout {
            Layout.topMargin: -5
            Layout.rightMargin: 5
            spacing: 1

            RowLayout {
                spacing: 4
                MaterialSymbol {
                    iconSize: Appearance.font.pixelSize.smaller
                    text: "wb_twilight"
                    color: Appearance.colors.colOnPrimaryContainer
                    opacity: 0.6
                }
                StyledText {
                    text: Weather.data?.sunrise ?? "--"
                    font.pixelSize: Appearance.font.pixelSize.smaller
                    color: Appearance.colors.colOnPrimaryContainer
                    opacity: 0.6
                }
            }

            RowLayout {
                spacing: 4
                MaterialSymbol {
                    iconSize: Appearance.font.pixelSize.smaller
                    text: "nights_stay"
                    color: Appearance.colors.colOnPrimaryContainer
                    opacity: 0.6
                }
                StyledText {
                    text: Weather.data?.sunset ?? "--"
                    font.pixelSize: Appearance.font.pixelSize.smaller
                    color: Appearance.colors.colOnPrimaryContainer
                    opacity: 0.6
                }
            }
        }
    }
}
