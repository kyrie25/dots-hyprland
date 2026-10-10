import qs.modules.common
import qs.modules.common.widgets
import QtQuick
import QtQuick.Layouts

StyledText {
    id: root
    property var widgetOptions: WidgetProfiles.forItem(parent)
    Layout.fillWidth: true
    font {
        family: root.widgetOptions.widgets.clock.quote.followClock
            ? root.widgetOptions.widgets.clock.digital.font.family
            : Appearance.font.family.expressive
        pixelSize: 20
        weight: 350
        // Set empty to prevent conflicts, not meaningless
        styleName: ""
        variableAxes: ({})
    }
    style: Text.Raised
    styleColor: Appearance.colors.colShadow
    animateChange: root.widgetOptions.widgets.clock.digital.animateChange
}
