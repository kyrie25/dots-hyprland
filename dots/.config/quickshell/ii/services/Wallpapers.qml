import qs.modules.common
import qs.modules.common.models
import qs.modules.common.functions
import QtQuick
import Qt.labs.folderlistmodel
import Quickshell
import Quickshell.Io
pragma Singleton
pragma ComponentBehavior: Bound

/**
 * Provides a list of wallpapers and an "apply" action that calls the existing
 * switchwall.sh script. Pretty much a limited file browsing service.
 */
Singleton {
    id: root

    property string thumbgenScriptPath: `${FileUtils.trimFileProtocol(Directories.scriptPath)}/thumbnails/thumbgen-venv.sh`
    property string generateThumbnailsMagickScriptPath: `${FileUtils.trimFileProtocol(Directories.scriptPath)}/thumbnails/generate-thumbnails-magick.sh`
    property alias directory: folderModel.folder
    readonly property string effectiveDirectory: FileUtils.trimFileProtocol(folderModel.folder.toString())
    property url defaultFolder: Qt.resolvedUrl(`${Directories.pictures}/Wallpapers`)
    property alias folderModel: folderModel // Expose for direct binding when needed
    property string searchQuery: ""
    property bool browsingWallpaperEngine: false
    property string wallpaperEngineDirectory: ""
    property list<var> wallpaperEngineItems: []
    readonly property list<var> filteredWallpaperEngineItems: wallpaperEngineItems.filter(item =>
        item.displayName.toLowerCase().includes(searchQuery.toLowerCase())
        || item.workshopId.includes(searchQuery)
        || item.wallpaperType.includes(searchQuery.toLowerCase()))
    readonly property list<string> extensions: [
        "jpg", "jpeg", "png", "webp", "avif", "bmp", "svg",
        "mp4", "webm", "mkv", "avi", "mov"
    ]
    readonly property list<string> videoExtensions: ["mp4", "webm", "mkv", "avi", "mov"]
    property list<string> wallpapers: [] // List of absolute file paths (without file://)
    readonly property bool thumbnailGenerationRunning: thumbgenProc.running || wallpaperEngineScanProc.running
    property real thumbnailGenerationProgress: 0
    property string wallpaperEngineRuntimeState: "running"

    signal changed()
    signal thumbnailGenerated(directory: string)
    signal thumbnailGeneratedFile(filePath: string)

    function load () {} // For forcing initialization
    
    function currentWallpaperPath(monitorName = "") {
        if (monitorName.length > 0) {
            const entry = (Config.options.background.wallpapersByMonitor || []).find(item => item.monitor === monitorName)
            if (entry?.path) return entry.path
        }
        return Config.options.background.wallpaperPath
    }

    function wallpaperForMonitor(monitorName) {
        const entry = (Config.options.background.wallpapersByMonitor || []).find(item => item.monitor === monitorName)
        const defaults = {
            monitor: monitorName,
            path: Config.options.background.wallpaperPath,
            thumbnailPath: Config.options.background.thumbnailPath,
            type: Config.options.background.wallpaperType,
            scaling: "fill",
            alignX: "center",
            alignY: "center",
            properties: ({})
        }
        return Object.assign(defaults, entry || {})
    }

    function updateMonitorWallpaperSetting(monitorName, key, value) {
        const current = Config.options.background.wallpapersByMonitor || []
        let found = false
        const updated = current.map(entry => {
            if (entry.monitor !== monitorName) return entry
            found = true
            const copy = Object.assign({}, entry)
            copy[key] = value
            return copy
        })
        if (!found) {
            const entry = Object.assign({}, wallpaperForMonitor(monitorName))
            entry[key] = value
            updated.push(entry)
        }
        Config.options.background.wallpapersByMonitor = updated
        scheduleWallpaperEngineRestart()
    }

    function updateWallpaperEngineProperty(monitorName, propertyName, value) {
        const entry = wallpaperForMonitor(monitorName)
        const properties = Object.assign({}, entry.properties || {})
        properties[propertyName] = value
        updateMonitorWallpaperSetting(monitorName, "properties", properties)
    }

    function resetWallpaperEngineProperty(monitorName, propertyName) {
        const entry = wallpaperForMonitor(monitorName)
        const properties = Object.assign({}, entry.properties || {})
        delete properties[propertyName]
        updateMonitorWallpaperSetting(monitorName, "properties", properties)
    }

    function scheduleWallpaperEngineRestart() {
        wallpaperEngineRestartTimer.restart()
    }

    function setWallpaperEnginePaused(paused) {
        Config.options.background.wallpaperEngine.paused = paused
        Quickshell.execDetached([Directories.wallpaperRuntimeScriptPath, paused ? "pause" : "resume"])
    }

    function openFallbackPicker(darkMode = Appearance.m3colors.darkmode, monitorName = "") {
        const command = [Directories.wallpaperSwitchScriptPath, "--mode", darkMode ? "dark" : "light"]
        if (monitorName.length > 0) command.push("--monitor", monitorName)
        Quickshell.execDetached(command);
    }

    function apply(path, darkMode = Appearance.m3colors.darkmode, monitorName = "") {
        if (!path || path.length === 0) return;
        const command = [Directories.wallpaperSwitchScriptPath, "--mode", darkMode ? "dark" : "light", "--image", path]
        if (monitorName.length > 0) command.push("--monitor", monitorName)
        Quickshell.execDetached(command);
        root.changed()
    }

    function openWallpaperEngineLibrary() {
        if (wallpaperEngineItems.length > 0) {
            browsingWallpaperEngine = true
            return
        }
        thumbnailGenerationProgress = 0
        wallpaperEngineScanProc.running = false
        wallpaperEngineScanProc.command = ["python3", Directories.wallpaperEngineScriptPath, "scan"]
        wallpaperEngineScanProc.running = true
    }

    Timer {
        id: wallpaperEngineRestartTimer
        interval: 500
        repeat: false
        onTriggered: Quickshell.execDetached([Directories.wallpaperRuntimeScriptPath, "restart"])
    }

    function updateWallpaperEngineRuntimeState() {
        if (!wallpaperEngineStateFile.loaded) return
        const state = wallpaperEngineStateFile.text().trim()
        if (["running", "muted", "paused", "stopped"].includes(state))
            root.wallpaperEngineRuntimeState = state
    }

    FileView {
        id: wallpaperEngineStateFile
        path: Qt.resolvedUrl(`${Directories.genericCache}/linux-wallpaperengine/state`)
        watchChanges: true
        onLoadedChanged: root.updateWallpaperEngineRuntimeState()
        onFileChanged: {
            reload()
            wallpaperEngineStateReadTimer.restart()
        }
    }

    Timer {
        id: wallpaperEngineStateReadTimer
        interval: 50
        repeat: false
        onTriggered: root.updateWallpaperEngineRuntimeState()
    }

    Process {
        id: selectProc
        property string filePath: ""
        property bool darkMode: Appearance.m3colors.darkmode
        property string monitorName: ""
        function select(filePath, darkMode = Appearance.m3colors.darkmode, monitorName = "") {
            selectProc.filePath = filePath
            selectProc.darkMode = darkMode
            selectProc.monitorName = monitorName
            selectProc.exec(["python3", Directories.wallpaperEngineScriptPath, "classify", FileUtils.trimFileProtocol(filePath)])
        }
        stdout: StdioCollector { id: selectOutput }
        onExited: (exitCode, exitStatus) => {
            const result = selectOutput.text.trim()
            if (result === "directory") {
                setDirectory(selectProc.filePath);
                return;
            }
            if (result === "file" || result === "wallpaper-engine")
                root.apply(selectProc.filePath, selectProc.darkMode, selectProc.monitorName);
        }
    }

    function select(filePath, darkMode = Appearance.m3colors.darkmode, monitorName = "") {
        selectProc.select(filePath, darkMode, monitorName);
    }

    function randomFromCurrentFolder(darkMode = Appearance.m3colors.darkmode, monitorName = "") {
        const count = browsingWallpaperEngine ? filteredWallpaperEngineItems.length : folderModel.count
        if (count === 0) return;
        const randomIndex = Math.floor(Math.random() * count);
        const filePath = browsingWallpaperEngine
            ? filteredWallpaperEngineItems[randomIndex].filePath
            : folderModel.get(randomIndex, "filePath");
        print("Randomly selected wallpaper:", filePath);
        root.select(filePath, darkMode, monitorName);
    }

    Process {
        id: validateDirProc
        property string nicePath: ""
        function setDirectoryIfValid(path) {
            validateDirProc.nicePath = FileUtils.trimFileProtocol(path).replace(/\/+$/, "")
            if (/^\/*$/.test(validateDirProc.nicePath)) validateDirProc.nicePath = "/";
            validateDirProc.exec([
                "bash", "-c",
                `if [ -d "${validateDirProc.nicePath}" ]; then echo dir; elif [ -f "${validateDirProc.nicePath}" ]; then echo file; else echo invalid; fi`
            ])
        }
        stdout: StdioCollector {
            onStreamFinished: {
                    root.directory = Qt.resolvedUrl(validateDirProc.nicePath)
                const result = text.trim()
                if (result === "dir") {
                } else if (result === "file") {
                    root.directory = Qt.resolvedUrl(FileUtils.parentDirectory(validateDirProc.nicePath))
                } else {
                    // Ignore
                }
            }
        }
    }
    function setDirectory(path) {
        browsingWallpaperEngine = false
        validateDirProc.setDirectoryIfValid(path)
    }
    function navigateUp() {
        folderModel.navigateUp()
    }
    function navigateBack() {
        folderModel.navigateBack()
    }
    function navigateForward() {
        folderModel.navigateForward()
    }

    // Folder model
    FolderListModelWithHistory {
        id: folderModel
        folder: Qt.resolvedUrl(root.defaultFolder)
        caseSensitive: false
        nameFilters: root.extensions.map(ext => `*${searchQuery.split(" ").filter(s => s.length > 0).map(s => `*${s}*`)}*.${ext}`)
        showDirs: true
        showDotAndDotDot: false
        showOnlyReadable: true
        sortField: FolderListModel.Time
        sortReversed: false
        onCountChanged: {
            root.wallpapers = []
            for (let i = 0; i < folderModel.count; i++) {
                const path = folderModel.get(i, "filePath") || FileUtils.trimFileProtocol(folderModel.get(i, "fileURL"))
                if (path && path.length) root.wallpapers.push(path)
            }
        }
    }

    // Thumbnail generation
    function generateThumbnail(size: string) {
        if (!["normal", "large", "x-large", "xx-large"].includes(size)) throw new Error("Invalid thumbnail size");
        if (browsingWallpaperEngine) return
        thumbgenProc.directory = root.directory
        thumbgenProc.running = false
        thumbgenProc.command = [
            "bash", "-c",
            `${thumbgenScriptPath} --size ${size} --machine_progress -d ${FileUtils.trimFileProtocol(root.directory)} || ${generateThumbnailsMagickScriptPath} --size ${size} -d ${FileUtils.trimFileProtocol(root.directory)}`,
        ]
        // console.log("[Wallpapers] Updating thumbnails with command ", thumbgenProc.command.join(" "))
        root.thumbnailGenerationProgress = 0
        thumbgenProc.running = true
    }
    Process {
        id: thumbgenProc
        property string directory
        stdout: SplitParser {
            onRead: data => {
                // print("thumb gen proc:", data)
                let match = data.match(/PROGRESS (\d+)\/(\d+)/)
                if (match) {
                    const completed = parseInt(match[1])
                    const total = parseInt(match[2])
                    root.thumbnailGenerationProgress = completed / total
                }
                match = data.match(/FILE (.+)/)
                if (match) {
                    const filePath = match[1]
                    root.thumbnailGeneratedFile(filePath)
                }
            }
        }
        onExited: (exitCode, exitStatus) => {
            // print("[Wallpapers] Thumbnail generation completed with exit code", exitCode)
            root.thumbnailGenerated(thumbgenProc.directory)
        }
    }

    Process {
        id: wallpaperEngineScanProc
        stdout: StdioCollector { id: wallpaperEngineScanOutput }
        stderr: StdioCollector { id: wallpaperEngineScanError }
        onExited: (exitCode, exitStatus) => {
            if (exitCode !== 0) {
                console.warn("[Wallpapers] Failed to scan Wallpaper Engine projects:", wallpaperEngineScanError.text.trim())
                return
            }
            try {
                root.wallpaperEngineItems = JSON.parse(wallpaperEngineScanOutput.text)
                if (root.wallpaperEngineItems.length > 0) {
                    root.wallpaperEngineDirectory = FileUtils.parentDirectory(root.wallpaperEngineItems[0].filePath)
                    root.browsingWallpaperEngine = true
                    root.thumbnailGenerationProgress = 1
                }
            } catch (error) {
                console.warn("[Wallpapers] Invalid Wallpaper Engine scan output:", error)
            }
        }
    }

    IpcHandler {
        target: "wallpapers"

        function apply(path: string): void {
            root.apply(path);
        }
    }
}
