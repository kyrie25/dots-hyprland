import qs.modules.common.models.quickToggles as QuickToggles
import qs.modules.common.widgets

QuickToggleButton {
    id: root
    property QuickToggles.VpnToggle toggleModel: QuickToggles.VpnToggle {}

    visible: toggleModel.available
    toggled: toggleModel.toggled
    buttonIcon: toggleModel.icon
    // Selecting a VPN requires choosing from the configured profiles.
    onClicked: root.altAction()

    StyledToolTip {
        text: toggleModel.tooltipText
    }
}
