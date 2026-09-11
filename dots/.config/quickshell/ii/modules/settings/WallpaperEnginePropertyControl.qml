pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import qs.services
import qs.modules.common
import qs.modules.common.functions
import qs.modules.common.widgets

RowLayout {
    id: root

    required property var definition
    property var effectiveValue
    property bool overridden: false

    signal edited(var value)
    signal resetRequested()

    Layout.fillWidth: true
    spacing: 6

    function boolValue(value) {
        return value === true || value === 1 || value === "1" || value === "true"
    }

    function decimalPlaces() {
        const step = Number(definition.step || 1)
        const text = String(step)
        return text.includes(".") ? text.length - text.indexOf(".") - 1 : 0
    }

    function colorValue(value) {
        const parts = String(value || "0 0 0").trim().split(/\s+/).map(Number)
        return Qt.rgba(parts[0] || 0, parts[1] || 0, parts[2] || 0, 1)
    }

    function serializedColor(value) {
        return [value.r, value.g, value.b].map(component => Number(component.toFixed(5))).join(" ")
    }

    Loader {
        Layout.fillWidth: true
        sourceComponent: {
            switch (root.definition.type) {
            case "bool": return boolControl
            case "slider": return sliderControl
            case "combo": return comboControl
            case "color": return colorControl
            default: return textControl
            }
        }
    }

    IconToolbarButton {
        visible: root.overridden
        Layout.fillHeight: false
        implicitWidth: 40
        implicitHeight: 40
        text: "restart_alt"
        onClicked: root.resetRequested()

        StyledToolTip {
            text: Translation.tr("Use the wallpaper's default value")
        }
    }

    Component {
        id: boolControl

        ConfigSwitch {
            text: root.definition.label
            buttonIcon: "toggle_on"
            checked: root.boolValue(root.effectiveValue)
            onCheckedChanged: {
                if (checked !== root.boolValue(root.effectiveValue))
                    root.edited(checked)
            }
        }
    }

    Component {
        id: sliderControl

        RowLayout {
            spacing: 10

            StyledText {
                Layout.preferredWidth: 180
                text: root.definition.label
                color: Appearance.colors.colOnSecondaryContainer
                elide: Text.ElideRight
            }

            StyledSlider {
                id: propertySlider
                from: Number(root.definition.min ?? 0)
                to: Number(root.definition.max ?? 1)
                stepSize: Number(root.definition.step ?? 0.01)
                value: Number(root.effectiveValue ?? root.definition.value ?? 0)
                snapMode: Slider.SnapAlways
                usePercentTooltip: false
                tooltipContent: value.toFixed(root.decimalPlaces())
                onMoved: root.edited(value)
            }

            StyledText {
                Layout.preferredWidth: 48
                horizontalAlignment: Text.AlignRight
                text: propertySlider.value.toFixed(root.decimalPlaces())
                color: Appearance.colors.colSubtext
            }
        }
    }

    Component {
        id: comboControl

        RowLayout {
            spacing: 10

            StyledText {
                Layout.preferredWidth: 180
                text: root.definition.label
                color: Appearance.colors.colOnSecondaryContainer
                elide: Text.ElideRight
            }

            StyledComboBox {
                model: root.definition.options || []
                textRole: "label"
                currentIndex: {
                    const value = String(root.effectiveValue)
                    const index = model.findIndex(option => String(option.value) === value)
                    return index >= 0 ? index : 0
                }
                onActivated: index => root.edited(model[index].value)
            }
        }
    }

    Component {
        id: colorControl

        RowLayout {
            spacing: 10

            StyledText {
                Layout.preferredWidth: 180
                text: root.definition.label
                color: Appearance.colors.colOnSecondaryContainer
                elide: Text.ElideRight
            }

            MaterialTextField {
                Layout.fillWidth: true
                text: String(root.effectiveValue ?? "")
                placeholderText: "0.0 0.0 0.0"
                onEditingFinished: {
                    if (text !== String(root.effectiveValue ?? ""))
                        root.edited(text)
                }
            }

            RippleButton {
                implicitWidth: 40
                implicitHeight: 40
                buttonRadius: Appearance.rounding.full
                onClicked: {
                    colorDialog.selectedColor = root.colorValue(root.effectiveValue)
                    colorDialog.open()
                }

                contentItem: Rectangle {
                    anchors.centerIn: parent
                    width: 22
                    height: 22
                    radius: Appearance.rounding.full
                    color: root.colorValue(root.effectiveValue)
                    border.width: 1
                    border.color: Appearance.colors.colOutline
                }
            }
        }
    }

    Component {
        id: textControl

        RowLayout {
            spacing: 10

            StyledText {
                Layout.preferredWidth: 180
                text: root.definition.label
                color: Appearance.colors.colOnSecondaryContainer
                elide: Text.ElideRight
            }

            MaterialTextField {
                Layout.fillWidth: true
                text: String(root.effectiveValue ?? "")
                placeholderText: root.definition.type === "textinput"
                    ? Translation.tr("Value")
                    : Translation.tr("File or directory path")
                onEditingFinished: {
                    if (text !== String(root.effectiveValue ?? ""))
                        root.edited(text)
                }
            }

            IconToolbarButton {
                visible: ["file", "directory", "scenetexture"].includes(root.definition.type)
                Layout.fillHeight: false
                implicitWidth: 40
                implicitHeight: 40
                text: "folder_open"
                onClicked: {
                    if (root.definition.type === "directory")
                        folderDialog.open()
                    else
                        fileDialog.open()
                }
            }
        }
    }

    ColorDialog {
        id: colorDialog
        title: root.definition.label
        onAccepted: root.edited(root.serializedColor(selectedColor))
    }

    FileDialog {
        id: fileDialog
        title: root.definition.label
        onAccepted: root.edited(FileUtils.trimFileProtocol(decodeURIComponent(selectedFile.toString())))
    }

    FolderDialog {
        id: folderDialog
        title: root.definition.label
        onAccepted: root.edited(FileUtils.trimFileProtocol(decodeURIComponent(selectedFolder.toString())))
    }
}
