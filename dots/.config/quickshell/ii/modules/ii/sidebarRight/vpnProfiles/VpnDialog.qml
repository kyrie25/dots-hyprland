import qs.modules.common
import qs.modules.common.widgets
import qs.services
import QtQuick
import QtQuick.Layouts
import Quickshell

WindowDialog {
    id: root
    backgroundHeight: 600

    WindowDialogTitle {
        text: "VPN"
    }
    WindowDialogSeparator {}
    StyledListView {
        Layout.fillHeight: true
        Layout.fillWidth: true
        Layout.topMargin: -15
        Layout.bottomMargin: -16
        Layout.leftMargin: -Appearance.rounding.large
        Layout.rightMargin: -Appearance.rounding.large

        clip: true
        spacing: 0
        animateAppearance: false

        model: ScriptModel {
            values: Network.vpnProfiles
        }
        delegate: VpnProfileItem {
            required property var modelData
            profile: modelData
            width: ListView.view.width
        }
    }
    WindowDialogSeparator {}
    WindowDialogButtonRow {
        Item {
            Layout.fillWidth: true
        }

        DialogButton {
            buttonText: Translation.tr("Done")
            onClicked: root.dismiss()
        }
    }
}
