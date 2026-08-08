import qs.modules.common
import qs.modules.common.widgets
import qs.services
import QtQuick
import QtQuick.Layouts

DialogListItem {
    id: root
    required property var profile

    active: profile?.active ?? false
    enabled: !Network.vpnConnecting
    onClicked: {
        if (profile?.active)
            Network.disconnectVpn(profile);
        else
            Network.connectVpn(profile);
    }

    contentItem: RowLayout {
        anchors {
            fill: parent
            topMargin: root.verticalPadding
            bottomMargin: root.verticalPadding
            leftMargin: root.horizontalPadding
            rightMargin: root.horizontalPadding
        }
        spacing: 10

        MaterialSymbol {
            iconSize: Appearance.font.pixelSize.larger
            text: "vpn_key"
            color: Appearance.colors.colOnSurfaceVariant
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            StyledText {
                Layout.fillWidth: true
                color: Appearance.colors.colOnSurfaceVariant
                elide: Text.ElideRight
                text: root.profile?.name ?? ""
                textFormat: Text.PlainText
            }
            StyledText {
                Layout.fillWidth: true
                visible: root.profile?.active ?? false
                font.pixelSize: Appearance.font.pixelSize.smaller
                color: Appearance.colors.colSubtext
                text: Translation.tr("Connected")
            }
        }
        MaterialSymbol {
            iconSize: Appearance.font.pixelSize.larger
            text: root.profile?.active ? "check" : Network.vpnConnectionTarget === root.profile?.name ? "progress_activity" : ""
            color: Appearance.colors.colOnSurfaceVariant
        }
    }
}
