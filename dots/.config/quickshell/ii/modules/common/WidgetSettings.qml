import Quickshell.Io

JsonObject {
    property JsonObject clock: JsonObject {
        property bool enable: true
        property bool showOnlyWhenLocked: false
        property string placementStrategy: "leastBusy" // "free", "leastBusy", "mostBusy"
        property real x: 100
        property real y: 100
        property string style: "cookie"        // Options: "cookie", "digital", "pixel"
        property string color: ""
        property string styleLocked: "cookie"  // Options: "cookie", "digital", "pixel"
        property JsonObject cookie: JsonObject {
            property bool aiStyling: false
            property int sides: 14
            property string dialNumberStyle: "full"   // Options: "dots" , "numbers", "full" , "none"
            property string hourHandStyle: "fill"     // Options: "classic", "fill", "hollow", "hide"
            property string minuteHandStyle: "medium" // Options "classic", "thin", "medium", "bold", "hide"
            property string secondHandStyle: "dot"    // Options: "dot", "line", "classic", "hide"
            property string dateStyle: "bubble"       // Options: "border", "rect", "bubble" , "hide"
            property bool timeIndicators: true
            property bool hourMarks: false
            property bool dateInClock: true
            property bool constantlyRotate: false
            property bool useSineCookie: false
        }
        property JsonObject digital: JsonObject {
            property bool adaptiveAlignment: true
            property bool showDate: true
            property bool animateChange: true
            property bool vertical: false
            property JsonObject font: JsonObject {
                property string family: "Google Sans Flex"
                property real weight: 350
                property real width: 100
                property real size: 90
                property real roundness: 0
            }
        }
        property JsonObject pixel: JsonObject {
            property string orientation: "vertical"
        }
        property JsonObject quote: JsonObject {
            property bool enable: false
            property string text: ""
            property bool followClock: false
        }
    }
    property JsonObject weather: JsonObject {
        property bool enable: false
        property string placementStrategy: "free" // "free", "leastBusy", "mostBusy"
        property real x: 400
        property real y: 100
        property string sizeMode: "1x3"
    }
    property JsonObject calendar: JsonObject {
        property bool enable: false
        property string placementStrategy: "free"
        property real x: 400
        property real y: 100
        property string sizeMode: "2x2"
    }
    property JsonObject worldClock: JsonObject {
        property bool enable: false
        property list<string> timezones: ["Australia/Sydney", "Asia/Tokyo", "Europe/London", "America/New_York"]
        property string placementStrategy: "free"
        property real x: 400
        property real y: 100
        property string sizeMode: "2x2"
    }
    property JsonObject notes: JsonObject {
        property bool enable: false
        property string placementStrategy: "free"
        property real x: 400
        property real y: 100
    }
    property JsonObject userCard: JsonObject {
        property bool enable: false
        property string placementStrategy: "free"
        property real x: 400
        property real y: 100
    }
    property JsonObject images: JsonObject {
        property bool enable: false
        property string placementStrategy: "free"
        property real x: 400
        property real y: 100
    }
    property JsonObject visualizer: JsonObject {
        property bool enable: false
        property string placementStrategy: "free"
        property real x: 0
        property real y: 0
    }
    property JsonObject customImage: JsonObject {
        property bool enable: false
        property string placementStrategy: "free"
        property real x: 400
        property real y: 100
        property string path: ""
        property string shape: "Cookie4Sided"
        property real size: 200
    }
    property JsonObject resources: JsonObject {
        property bool enable: false
        property string placementStrategy: "free"
        property real x: 400
        property real y: 100
        property bool vertical: false
    }
    property JsonObject media: JsonObject {
        property bool enable: false
        property bool showControls: true
        property bool showLyrics: false
        property bool showTitles: true
        property string backgroundShape: "Cookie4Sided"
        property string placementStrategy: "free"
        property real x: 800
        property real y: 500
        property string sizeMode: "1x3"
    }
}
