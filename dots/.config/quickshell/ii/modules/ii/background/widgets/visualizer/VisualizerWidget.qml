import QtQuick
import qs
import qs.modules.common
import qs.modules.ii.background.widgets

AbstractBackgroundWidget {
    id: root

    configEntryName: "visualizer"

    readonly property list<real> points: GlobalStates.visualizerPoints
    property real barWidth: 4
    property real barSpacing: 8
    property real maxBarHeight: 220
    property real maxVisualizerValue: 1000
    property real smoothingDuration: 150
    property real activityOpacity: 0

    readonly property int barCount: Math.max(1, Math.floor(screenWidth / (barWidth + barSpacing)))
    readonly property var smoothedPoints: {
        const raw = points
        if (!raw || raw.length === 0)
            return Array(barCount).fill(0)

        const mapped = new Array(barCount)
        const rawLastIndex = raw.length - 1
        for (let i = 0; i < barCount; i++) {
            const progress = i / (barCount - 1 || 1)
            const relativePosition = progress * rawLastIndex
            const low = Math.floor(relativePosition)
            const high = Math.ceil(relativePosition)
            const mix = relativePosition - low
            mapped[i] = raw[low] * (1 - mix) + raw[high] * (high < raw.length ? mix : 0)
        }

        const smoothed = new Array(barCount)
        const sideWeight = 0.2
        for (let i = 0; i < barCount; i++) {
            const previous = mapped[Math.max(0, i - 1)]
            const next = mapped[Math.min(barCount - 1, i + 1)]
            smoothed[i] = previous * sideWeight + mapped[i] * (1 - 2 * sideWeight) + next * sideWeight
        }
        return smoothed
    }

    implicitWidth: screenWidth
    implicitHeight: maxBarHeight + 20
    x: 0
    y: screenHeight - implicitHeight
    draggable: false

    Behavior on activityOpacity {
        NumberAnimation {
            duration: 500
            easing.type: Easing.OutCubic
        }
    }

    Timer {
        id: silenceTimer
        interval: 1000
        onTriggered: root.activityOpacity = 0
    }

    onPointsChanged: {
        if (points.some(point => point > 0)) {
            root.activityOpacity = 1
            silenceTimer.restart()
        }
    }

    Row {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: root.barSpacing
        opacity: root.activityOpacity

        Behavior on opacity {
            NumberAnimation {
                duration: 400
                easing.type: Easing.OutCubic
            }
        }

        Repeater {
            model: root.barCount

            Rectangle {
                required property int index
                property real pointValue: {
                    const value = root.smoothedPoints[index] ?? 0
                    return Math.max(root.barWidth, value / root.maxVisualizerValue * root.maxBarHeight)
                }
                property real intensity: pointValue / root.maxBarHeight

                anchors.bottom: parent.bottom
                width: root.barWidth
                height: pointValue
                topLeftRadius: root.barWidth / 2
                topRightRadius: root.barWidth / 2
                color: Qt.rgba(
                    Appearance.colors.colPrimary.r * intensity + Appearance.colors.colPrimaryContainer.r * (1 - intensity),
                    Appearance.colors.colPrimary.g * intensity + Appearance.colors.colPrimaryContainer.g * (1 - intensity),
                    Appearance.colors.colPrimary.b * intensity + Appearance.colors.colPrimaryContainer.b * (1 - intensity),
                    1
                )

                Behavior on height {
                    NumberAnimation {
                        duration: root.smoothingDuration
                        easing.type: Easing.OutQuad
                    }
                }
            }
        }
    }
}
