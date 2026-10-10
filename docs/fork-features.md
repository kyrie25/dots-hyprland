# Fork features and fixes

This guide catalogs the additions in [kyrie25/dots-hyprland](https://github.com/kyrie25/dots-hyprland),
branch `main`, compared with [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland),
branch `main`. The comparison was checked on 2026-10-10 against upstream
`c4f0582cbf4ad29607dbf3c20337815de8690b34`, with fork implementation through
`66de76f9bc4339633bf2ce2f0a7b45296ca2e2ed`.

This includes locally developed fixes, selected upstream PRs, and adaptations
from other forks that are absent from that upstream baseline. Ordinary upstream
features and changes already merged into upstream are not claimed as additions.

## Wallpaper Engine on Wayland

### Selection and settings

- Wallpaper Engine is a wallpaper source in Quickshell settings, alongside
  static images and video wallpapers. Select a monitor and assign its project
  independently; previews show that monitor's selected Wallpaper Engine project
  rather than the previous static wallpaper.
- Theme color extraction uses the selected color-source image or project preview
  instead of trying to sample a video/project directory as a static image.
- Workshop discovery and project metadata/property parsing provide controls for
  exposed wallpaper properties, including custom image/file paths, colors,
  sliders, choices, and booleans. Property overrides are stored per monitor and
  can be reset to the project's defaults. Boolean controls use their button state
  without a redundant toggle label.
- Each monitor has its own wallpaper, scaling mode (`fill`, `fit`, `stretch`, or
  `default`), horizontal/vertical crop alignment, property overrides, and mute.
  Global mute remains available in addition to individual wallpaper mute.
- Playback settings expose manual pause, volume, FPS, anti-aliasing, audio
  processing, particles, mouse input, and parallax. The settings layout gives
  controls room, keeps the Light/Dark selector visible, and aligns behavior
  dropdowns consistently.
- Runtime status is visible in settings. FPS, volume/mute, scaling, and alignment
  use live control files with the supported renderer; changes requiring a reload
  restart the affected outputs. These controls do not imply separate per-monitor
  FPS or quality selectors: the shared performance settings are applied to each
  independent renderer.

### Automatic behavior

Configure Keep playing, Pause, Stop, or Mute for fullscreen windows, tiled
windows, and another application's audio playback.

| Trigger | Meaning and scope |
| --- | --- |
| Fullscreen | A true Hyprland fullscreen window on the monitor's visible workspace; optionally only the focused application. |
| Maximized | A non-floating, tiled window on the monitor's visible workspace, rather than only a compositor maximize flag. |
| Other app playing audio | Global: another application's active audio can affect wallpapers on all monitors. Wallpaper-owned streams are excluded. |

Workspace and window changes are reevaluated, so moving from an empty workspace
to a tiled one applies that monitor's rule without pausing an unrelated monitor.
A three-second startup grace lets newly started wallpapers render before
automatic pause/stop behavior can suspend them, preventing the initial black
background after reload. Manual pause and persistent mute remain explicit user
choices; the same grace also temporarily defers manual pause, while mute remains
effective. Overlapping policies resolve to the strongest applicable action.

### Runtime reliability and renderer dependency

- A supervisor owns a separate process session for each output, manages the
  renderer and its CEF audio children, and prevents duplicate supervisors.
  Session ownership makes mute/pause/cleanup work for Chromium audio as well as
  native scenes, and prevents wallpapers from triggering their own other-app
  audio policy.
- Settings files are replaced atomically. Live updates avoid unnecessary
  restarts; older renderers have a restart-based fallback. Pending live settings
  are applied after a suspended renderer resumes.
- Boolean parsing preserves explicit `false` settings instead of treating them
  as missing defaults, fixing ineffective unmute, audio-processing, particle,
  mouse, parallax, and focused-only toggles.
- The runtime handles renderer crashes, changed output configurations, and
  disconnected/reconnected outputs. Library-update recovery addresses a
  renderer failing to start after system upgrades.
- The existing Intel offload condition selects Mesa EGL while preserving an
  explicit vendor override. This is not a guarantee of every NVIDIA/VRAM setup.
- The renderer is a separate fork, tracked as a pinned submodule and packaged
  as `illogical-impulse-linux-wallpaperengine-git`. The Arch build disables X11
  discovery, verifies renderer/nested dependency revisions, excludes tests from
  the installed payload, and retains the renderer and msdfgen licenses.
- Renderer fixes cover text/widget drift, puppet animation and effects, media
  selection and artwork, custom images, encoded animation timing, native
  SceneScript, stereo spectra, and Wayland lifecycle. See its
  [complete feature catalog](https://github.com/kyrie25/linux-wallpaperengine/blob/ii-puppet-multimonitor/docs/fork-features.md)
  and [port attribution and validation](https://github.com/kyrie25/linux-wallpaperengine/blob/ii-puppet-multimonitor/docs/port-adaptations.md)
  for the implementation and limits.

## Desktop widgets and wallpaper presentation

- A desktop right-click menu provides a wallpaper carousel, palette selection,
  wallpaper styling, widget toggles/position locking, DropShelf, live-wallpaper
  selection, and Settings. It also exposes `desktopMenu open`, `close`, and
  `toggle` through Quickshell IPC.
- Draggable widgets snap to a 12-pixel placement grid. An optional 24-pixel
  alignment grid and screen-center guides appear during dragging; optional
  release guides highlight alignment after dropping. Drag bindings are restored
  correctly, including clock centering on the lock screen.
- Independent monitor profiles persist widget enables, positions, sizing,
  styles, and position locks in `widgets-<encoded-monitor-name>.json` under the
  shell configuration directory. New profiles are seeded once from the shared
  settings; Desktop Settings and the context menu edit the selected monitor.
- The widget collection adds Calendar, World Clock, Notes, User Card, Custom
  Image, Image Converter, Resources, Media, and a desktop Visualizer alongside
  the expanded Clock and Weather presentations. Notes persist; World Clock
  supports configurable timezones; Media supports controls, titles, lyrics,
  background shapes, and size modes; Custom Image has shape and size controls.
  Media cover clicks can select the active MPRIS player or invoke the widget's
  configured action.
- Clock adds horizontal/vertical Pixel presentation, selected digital colors,
  and quote/font options. Weather has resizable `1x1`, `1x2`, and `1x3` cards.
  Calendar, World Clock, and Image Converter use the ported translucent styling.
- The bottom-edge Cava visualizer shares samples with media controls, smooths
  and colors bars, and fades after silence. Per-monitor widget enables keep it
  available when needed by any monitor.
- Lock-screen widgets include clock and expanded weather. The desktop and lock
  screen share the expanded weather content so displayed fields stay consistent.
- Centered wallpaper styling provides shape, color, size, and lock-only options.
  Shader transitions and palette controls are available from both the context
  menu and Desktop Settings, preserving the existing parallax renderer.
- DropShelf provides a separate panel for the shelf action.
- Video wallpaper selection includes generated thumbnails. Detached `mpvpaper`
  startup survives the launching shell's exit; startup restoration integrates
  with the Wallpaper Engine supervisor instead of racing it.

## Peripheral batteries

- A draggable desktop card and indicators beside the bar's system resources
  display connected Bluetooth, OpenRazer, and UPower peripheral batteries.
  The shared reader polls every 30 seconds while a card or bar consumer exists.
- Reports are deduplicated across sources. Unknown percentages, charging,
  low battery, and individual source failures are represented; computer
  batteries, AC supplies, UPS devices, and monitors are excluded.
- The bar shows up to three devices, or one in its narrow layout, with an overflow
  count and a popup listing all devices. It replaces the earlier Bluetooth-only
  indicator. Desktop card settings and placement are per monitor.
- `python-dbus` is required; OpenRazer support additionally needs its Python
  bindings and user daemon. Device firmware/driver support determines available
  readings. See [usage, dependencies, and tests](../tests/peripheral-batteries/README.md).

## Dock, networking, music, and AI fixes

- Dock context menus add desktop-entry actions with mapped icons, new-instance
  launch, workspace moves, pin/unpin, and close-window actions. Pinned applications
  can be reordered by dragging, with the order persisted.
- Stable dock entry identities avoid replaying icon wipe animations whenever
  windows open or close. Preview screencopy is gated on visibility to avoid the
  reported Hyprland 0.54 crash; application search caches deduplicated entries
  instead of rebuilding them repeatedly, retaining desktop-entry retry handling.
- Window-title events are debounced separately from general Hyprland refreshes,
  preventing rapid title churn from monopolizing the shell.
- NetworkManager VPN/WireGuard profiles have quick toggles and a profile dialog
  with connect/disconnect status. Opening the toggle exposes the list. Escaped
  profile names are parsed correctly, and the network label identifies the
  physical Wi-Fi/Ethernet connection rather than a VPN.
- Network refreshes are serialized and pending work is retried after processes
  finish, including failed launches. This fixes rapid network-state changes
  reentering processes and crashing Quickshell. The Wi-Fi dialog adds explicit
  rescan controls with corrected button coloring.
- SongRec detection validates a real match with complete track fields and uses
  timed FIFO reads, fixing missed recognition/timeout handling. Recognized-track
  notifications fetch/cache cover art and retain notification actions.
- OpenAI-compatible sidebar AI supports streamed tool-call assembly, structured
  assistant/tool history and follow-up requests, and valid object schemas for
  parameterless tools. This enables an approved tool execution to return its
  result and continue the conversation, including OpenRouter/local-compatible
  models; execution still follows the shell's existing approval flow.

## Packaging and development additions

- The Arch widget dependencies include FFmpeg, mpvpaper, and the pinned renderer;
  installation initializes the renderer submodule before its local package.
  Backlight packaging selects `brightnessctl-git`.
- Quickshell packaging vendors cpptrace and removes its transitively installed
  libdwarf/zstd development artifacts to avoid system-package conflicts.
- The `merge-prs` helper is installed to `~/.local/bin`, which is added to shell
  and Hyprland PATH. Installation modes sync that directory and back it up when
  appropriate. VS Code QML import generation makes virtual `qs.*` modules
  discoverable by qmlls; its checked-in editor paths need adjustment on other
  machines.
- Hyprland startup no longer forces the previous hard-coded cursor theme.

## Installing this fork

The upstream download command in the inherited README installs upstream. To use
these additions, clone this fork and run its setup from the checkout:

```sh
git clone --recurse-submodules https://github.com/kyrie25/dots-hyprland.git
cd dots-hyprland
./setup install
```

The documented renderer packaging targets Arch. Wallpaper Engine assets still
require the official Steam installation; workshop compatibility is partial.
Do not substitute the ordinary AUR renderer and expect these fork-specific fixes.

## Verification and compatibility limits

The published renderer implementation passed 1,551 assertions in 99 cases and
isolated Wayland tests on two outputs. The 17 scripts in
[`tests/wallpaperengine`](../tests/wallpaperengine) cover render/media/native-script
paths, per-output policy, startup grace, crash/reconnect handling, and scene/web
audio. They create temporary fixtures; consult each script's prerequisites before
running tests in a live Wayland session.

Widget profile tests cover initial migration, independent persistence across
restart, and component loading. Peripheral tests cover source filtering,
deduplication, unknown/zero values, charging, and source failures. Commands:

```sh
bash tests/quickshell-widget-profiles/run.sh
python3 -m unittest discover -s tests/peripheral-batteries -v
```

These results do not establish universal Windows parity. KAngel blink cadence
and hair motion remain unverified; full 3D/HDR and parts of SceneScript remain
incomplete. Virtual-output reconnect checks do not establish all physical hotplug
or compositor-hidden behavior. Live Razer readings were verified, while hardware
Bluetooth battery verification remains pending. Earlier shell/dock/network
ports are cataloged from their retained source changes, not claimed to have
received the entire renderer regression suite.

## Attribution

The base shell is end-4's illogical-impulse. Desktop widgets, grid/menu,
presentation, and supporting services were adapted from
[pctrade/end4-pC](https://github.com/pctrade/end4-pC/tree/d0957d2c30a1a22fb011244113663cd061339313).
Selected upstream PRs retained in the fork include dock/context-menu, video
wallpaper, Wi-Fi rescan, application-search, network reliability, title-churn,
and AI tool-call fixes; their original authors remain in Git history.
Renderer port origins and license references are recorded in its
[port-adaptations guide](https://github.com/kyrie25/linux-wallpaperengine/blob/ii-puppet-multimonitor/docs/port-adaptations.md).
