import qs.modules.common.models.quickToggles as QuickToggles
import qs.services

AndroidQuickToggleButton {
    id: root

    toggleModel: QuickToggles.VpnToggle {
        mainAction: () => {
            if (Network.primaryVpnProfile) {
                Network.disconnectVpn(Network.primaryVpnProfile);
            } else if (Network.vpnProfiles.length > 1) {
                root.openMenu();
            } else if (Network.vpnProfiles.length === 1) {
                Network.connectVpn(Network.vpnProfiles[0]);
            }
        }
    }
}
