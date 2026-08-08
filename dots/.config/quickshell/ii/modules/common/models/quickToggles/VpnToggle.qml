import QtQuick
import qs.services
import qs.modules.common

QuickToggleModel {
    name: "VPN"
    statusText: Network.primaryVpnProfile?.name ?? Translation.tr("Not connected")
    tooltipText: Translation.tr("%1 | Right-click to configure").arg(statusText)
    icon: "vpn_key"

    available: Network.vpnProfiles.length > 0
    toggled: Network.activeVpnProfiles.length > 0
    mainAction: () => {
        if (Network.primaryVpnProfile)
            Network.disconnectVpn(Network.primaryVpnProfile);
        else if (Network.vpnProfiles.length === 1)
            Network.connectVpn(Network.vpnProfiles[0]);
    }
    hasMenu: true
}
