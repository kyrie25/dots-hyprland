
import qs.services
import qs.modules.common
import qs.modules.common.widgets
import QtQuick

Rectangle {
    id: rect
    property var widgetOptions: WidgetProfiles.forItem(parent)
    readonly property string dialStyle: rect.widgetOptions.widgets.clock.cookie.dialNumberStyle

    StyledText {
        anchors.centerIn: parent
        color: Appearance.colors.colSecondaryHover
        text: Qt.locale().toString(DateTime.clock.date, "dd")
        font {
            family: Appearance.font.family.expressive
            pixelSize: 20
            weight: 1000
        }
    }
}
