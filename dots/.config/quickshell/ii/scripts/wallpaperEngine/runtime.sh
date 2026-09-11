#!/usr/bin/env bash

set -u

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
CONFIG_FILE="$XDG_CONFIG_HOME/illogical-impulse/config.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER="$SCRIPT_DIR/wallpaper-engine.py"
LOG_DIR="$XDG_CACHE_HOME/linux-wallpaperengine"
STATE_FILE="$LOG_DIR/state"
VIDEO_OPTS="no-audio loop hwdec=auto scale=bilinear interpolation=no video-sync=display-resample panscan=1.0 video-scale-x=1.0 video-scale-y=1.0 video-align-x=0.5 video-align-y=0.5 load-scripts=no"
UNIT_PREFIX="illogical-impulse-wallpaper"
ENGINE_PATTERN='^(\./|/[^ ]*/)?linux-wallpaperengine( |$)'
renderer_pids=()

write_state() {
    mkdir -p "$LOG_DIR"
    printf '%s\n' "$1" >"$STATE_FILE.tmp"
    mv "$STATE_FILE.tmp" "$STATE_FILE"
}

stop_renderers() {
    local -a units=()
    if command -v systemctl >/dev/null 2>&1; then
        mapfile -t units < <(
            systemctl --user list-units --all --type=service --no-legend --plain "$UNIT_PREFIX-*.service" 2>/dev/null \
                | awk '{print $1}'
        )
        if [[ ${#units[@]} -gt 0 ]]; then
            systemctl --user stop "${units[@]}" >/dev/null 2>&1 || true
        fi
    fi

    pkill -f "$ENGINE_PATTERN" 2>/dev/null || true
    pkill -x mpvpaper 2>/dev/null || true
    for _ in {1..40}; do
        if ! pgrep -f "$ENGINE_PATTERN" >/dev/null 2>&1 \
            && ! pgrep -x mpvpaper >/dev/null 2>&1; then
            sleep 0.2
            write_state stopped
            return
        fi
        sleep 0.05
    done
}

signal_renderers() {
    local signal="$1"
    pkill "-$signal" -f "$ENGINE_PATTERN" 2>/dev/null || true
    pkill "-$signal" -x mpvpaper 2>/dev/null || true
}

pause_renderers() {
    signal_renderers STOP
    write_state paused
}

resume_renderers() {
    signal_renderers CONT
    write_state running
}

wallpaper_type() {
    local path="$1"
    local configured_type="$2"
    if [[ "$configured_type" != "" && "$configured_type" != "auto" && "$configured_type" != "null" ]]; then
        printf '%s\n' "$configured_type"
    elif [[ -d "$path" && -f "$path/project.json" ]]; then
        printf '%s\n' "wallpaper-engine"
    elif [[ "$path" =~ \.(mp4|webm|mkv|avi|mov)$ ]]; then
        printf '%s\n' "video"
    else
        printf '%s\n' "image"
    fi
}

find_engine() {
    if [[ -x /usr/bin/linux-wallpaperengine ]]; then
        printf '%s\n' /usr/bin/linux-wallpaperengine
    elif command -v linux-wallpaperengine >/dev/null 2>&1; then
        command -v linux-wallpaperengine
    elif [[ -x "$HOME/.local/bin/linux-wallpaperengine" ]]; then
        printf '%s\n' "$HOME/.local/bin/linux-wallpaperengine"
    else
        return 1
    fi
}

stop_children() {
    [[ ${#renderer_pids[@]} -gt 0 ]] || return
    kill -CONT "${renderer_pids[@]}" 2>/dev/null || true
    kill -TERM "${renderer_pids[@]}" 2>/dev/null || true
    wait "${renderer_pids[@]}" 2>/dev/null || true
    renderer_pids=()
}

renderers_alive() {
    [[ ${#renderer_pids[@]} -gt 0 ]] || return 1
    local pid
    for pid in "${renderer_pids[@]}"; do
        kill -0 "$pid" 2>/dev/null || return 1
    done
}

property_args() {
    local properties="$1"
    local encoded_name encoded_value name value
    while IFS=$'\t' read -r encoded_name encoded_value; do
        [[ -n "$encoded_name" ]] || continue
        name="$(printf '%s' "$encoded_name" | base64 -d)"
        value="$(printf '%s' "$encoded_value" | base64 -d)"
        printf '%s\0%s\0' --set-property "$name=$value"
    done < <(jq -r '
        to_entries[]
        | [.key, (if .value == true then "1" elif .value == false then "0" else (.value | tostring) end)]
        | map(@base64)
        | @tsv
    ' <<<"$properties")
}

start_renderers() {
    [[ -f "$CONFIG_FILE" ]] || return 0

    local engine=""
    local assets=""
    engine="$(find_engine 2>/dev/null || true)"
    assets="$(python3 "$HELPER" locate assets 2>/dev/null || true)"
    mkdir -p "$LOG_DIR"

    local settings
    settings="$(jq -c '.background.wallpaperEngine // {}' "$CONFIG_FILE")"
    local fps anti_aliasing muted volume audio_processing particles mouse_input parallax
    fps="$(jq -r '.fps // 30' <<<"$settings")"
    anti_aliasing="$(jq -r '.antiAliasing // 4' <<<"$settings")"
    muted="$(jq -r 'if has("muted") then .muted else true end' <<<"$settings")"
    volume="$(jq -r '.volume // 15' <<<"$settings")"
    audio_processing="$(jq -r 'if has("audioProcessing") then .audioProcessing else true end' <<<"$settings")"
    particles="$(jq -r 'if has("particles") then .particles else true end' <<<"$settings")"
    mouse_input="$(jq -r 'if has("mouseInput") then .mouseInput else true end' <<<"$settings")"
    parallax="$(jq -r 'if has("parallax") then .parallax else true end' <<<"$settings")"

    local -a common_args=(
        --fps "$fps" --anti-aliasing "$anti_aliasing" --no-fullscreen-pause --noautomute
        --layer background --assets-dir "$assets"
    )
    if [[ "$muted" == true ]]; then
        common_args+=(--silent)
    else
        common_args+=(--volume "$volume")
    fi
    [[ "$audio_processing" == true ]] || common_args+=(--no-audio-processing)
    [[ "$particles" == true ]] || common_args+=(--disable-particles)
    [[ "$mouse_input" == true ]] || common_args+=(--disable-mouse)
    [[ "$parallax" == true ]] || common_args+=(--disable-parallax)

    local -a engine_monitors=()
    local -a engine_paths=()
    local -a engine_scalings=()
    local -a engine_align_x=()
    local -a engine_align_y=()
    local -a engine_properties=()
    local first_engine_path=""
    local monitor entry path type configured_type scaling align_x align_y properties
    while IFS= read -r monitor; do
        [[ -n "$monitor" ]] || continue
        entry="$(jq -c --arg monitor "$monitor" '
            ((.background.wallpapersByMonitor // []) | map(select(.monitor == $monitor)) | .[0]) as $entry
            | {
                path: ($entry.path // .background.wallpaperPath // ""),
                type: ($entry.type // .background.wallpaperType // "auto"),
                scaling: ($entry.scaling // "fill"),
                alignX: ($entry.alignX // "center"),
                alignY: ($entry.alignY // "center"),
                properties: ($entry.properties // {})
            }
        ' "$CONFIG_FILE")"
        path="$(jq -r '.path' <<<"$entry")"
        configured_type="$(jq -r '.type' <<<"$entry")"
        [[ -n "$path" && "$path" != "null" ]] || continue
        type="$(wallpaper_type "$path" "$configured_type")"

        case "$type" in
            wallpaper-engine)
                [[ -n "$engine" && -n "$assets" ]] || continue
                scaling="$(jq -r '.scaling' <<<"$entry")"
                align_x="$(jq -r '.alignX' <<<"$entry")"
                align_y="$(jq -r '.alignY' <<<"$entry")"
                properties="$(jq -c '.properties' <<<"$entry")"
                engine_monitors+=("$monitor")
                engine_paths+=("$path")
                engine_scalings+=("$scaling")
                engine_align_x+=("$align_x")
                engine_align_y+=("$align_y")
                engine_properties+=("$properties")
                [[ -n "$first_engine_path" ]] || first_engine_path="$path"
                ;;
            video)
                command -v mpvpaper >/dev/null 2>&1 || continue
                mpvpaper -o "$VIDEO_OPTS" "$monitor" "$path" >"$LOG_DIR/mpvpaper-$monitor.log" 2>&1 &
                renderer_pids+=("$!")
                ;;
        esac
    done < <(hyprctl monitors -j | jq -r '.[].name')

    if [[ ${#engine_monitors[@]} -gt 0 ]]; then
        local -a engine_env=(__GL_THREADED_OPTIMIZATIONS=0)
        if [[ "${AQ_DRM_DEVICES:-}" == *nvidia*:*intel* ]]; then
            engine_env+=(DRI_PRIME=1 LIBVA_DRIVER_NAME=iHD)
        fi

        local split_processes=false
        local properties_json
        for properties_json in "${engine_properties[@]}"; do
            if [[ "$(jq 'length' <<<"$properties_json")" -gt 0 ]]; then
                split_processes=true
                break
            fi
        done

        if [[ "$split_processes" == true ]]; then
            local index safe_monitor
            for index in "${!engine_monitors[@]}"; do
                local -a overrides=()
                mapfile -d '' -t overrides < <(property_args "${engine_properties[$index]}")
                safe_monitor="${engine_monitors[$index]//[^A-Za-z0-9_.-]/_}"
                env -u __GLX_VENDOR_LIBRARY_NAME "${engine_env[@]}" "$engine" \
                    "${common_args[@]}" \
                    --screen-root "${engine_monitors[$index]}" \
                    --bg "${engine_paths[$index]}" \
                    --scaling "${engine_scalings[$index]}" \
                    --align-x "${engine_align_x[$index]}" \
                    --align-y "${engine_align_y[$index]}" \
                    "${overrides[@]}" "${engine_paths[$index]}" \
                    >"$LOG_DIR/runtime-$safe_monitor.log" 2>&1 &
                renderer_pids+=("$!")
            done
        else
            local -a engine_args=()
            local index
            for index in "${!engine_monitors[@]}"; do
                engine_args+=(
                    --screen-root "${engine_monitors[$index]}"
                    --bg "${engine_paths[$index]}"
                    --scaling "${engine_scalings[$index]}"
                    --align-x "${engine_align_x[$index]}"
                    --align-y "${engine_align_y[$index]}"
                )
            done
            env -u __GLX_VENDOR_LIBRARY_NAME "${engine_env[@]}" "$engine" \
                "${common_args[@]}" "${engine_args[@]}" "$first_engine_path" \
                >"$LOG_DIR/runtime.log" 2>&1 &
            renderer_pids+=("$!")
        fi
    fi

    [[ ${#renderer_pids[@]} -gt 0 ]]
}

other_audio_playing() {
    command -v pactl >/dev/null 2>&1 || return 1
    pactl -f json list sink-inputs 2>/dev/null | jq -e '
        any(.[];
            (.corked == false)
            and (.mute != true)
            and ((.properties."application.name" // "") != "linux-wallpaperengine")
            and (([.volume[].value] | max // 0) > 0)
        )
    ' >/dev/null
}

window_states() {
    local monitors clients active_only
    monitors="$(hyprctl monitors -j 2>/dev/null || printf '[]')"
    clients="$(hyprctl clients -j 2>/dev/null || printf '[]')"
    active_only="$(jq -r '(.background.wallpaperEngine.behavior // {}) | if has("fullscreenOnlyActive") then .fullscreenOnlyActive else true end' "$CONFIG_FILE")"
    jq -nr --argjson monitors "$monitors" --argjson clients "$clients" --argjson activeOnly "$active_only" '
        [$monitors[].activeWorkspace.id] as $activeWorkspaces
        | [$clients[]
            | select(.hidden != true)
            | select(.workspace.id as $workspace | $activeWorkspaces | index($workspace))
        ] as $visible
        | [
            any($visible[];
                (((.fullscreen // 0) == 2) or ((.fullscreen // 0) == 3))
                and (($activeOnly | not) or ((.focusHistoryID // -1) == 0))
            ),
            any($visible[];
                (.floating == false)
                and (((.fullscreen // 0) == 0) or ((.fullscreen // 0) == 1))
            )
        ]
        | @tsv
    '
}

desired_action() {
    local fullscreen maximized
    IFS=$'\t' read -r fullscreen maximized < <(window_states)
    local -a actions=()
    [[ "$fullscreen" == true ]] && actions+=("$(jq -r '.background.wallpaperEngine.behavior.fullscreen // "pause"' "$CONFIG_FILE")")
    [[ "$maximized" == true ]] && actions+=("$(jq -r '.background.wallpaperEngine.behavior.maximized // "keep"' "$CONFIG_FILE")")
    other_audio_playing && actions+=("$(jq -r '.background.wallpaperEngine.behavior.audioPlaying // "keep"' "$CONFIG_FILE")")
    [[ "$(jq -r '.background.wallpaperEngine.paused // false' "$CONFIG_FILE")" == true ]] && actions+=(pause)

    local result=keep action
    for action in "${actions[@]}"; do
        case "$action:$result" in
            stop:*) result=stop ;;
            pause:keep|pause:mute) result=pause ;;
            mute:keep) result=mute ;;
        esac
    done
    printf '%s\n' "$result"
}

set_renderer_audio_mute() {
    local muted="$1"
    command -v pactl >/dev/null 2>&1 || return
    local index
    while IFS= read -r index; do
        [[ -n "$index" ]] && pactl set-sink-input-mute "$index" "$muted" >/dev/null 2>&1 || true
    done < <(pactl -f json list sink-inputs 2>/dev/null | jq -r '.[] | select((.properties."application.name" // "") == "linux-wallpaperengine") | .index')
}

run_renderers() {
    [[ -f "$CONFIG_FILE" ]] || return 0
    mkdir -p "$LOG_DIR"
    trap 'stop_children; write_state stopped' EXIT INT TERM

    start_renderers || {
        write_state stopped
        return 0
    }
    write_state running

    local last_action=""
    while true; do
        local action
        action="$(desired_action)"

        if [[ "$action" != stop ]] && ! renderers_alive; then
            stop_children
            start_renderers || return 0
            last_action=""
        fi

        case "$action" in
            stop)
                if [[ "$last_action" != stop ]]; then
                    stop_children
                    write_state stopped
                fi
                ;;
            pause)
                if [[ "$last_action" == stop ]]; then
                    start_renderers || return 0
                fi
                if [[ "$last_action" != pause ]]; then
                    [[ "$last_action" == mute ]] && set_renderer_audio_mute 0
                    signal_renderers STOP
                    write_state paused
                fi
                ;;
            mute)
                if [[ "$last_action" == stop ]]; then
                    start_renderers || return 0
                fi
                [[ "$last_action" == pause ]] && signal_renderers CONT
                set_renderer_audio_mute 1
                [[ "$last_action" == mute ]] || write_state muted
                ;;
            keep|*)
                if [[ "$last_action" == stop ]]; then
                    start_renderers || return 0
                fi
                [[ "$last_action" == pause ]] && signal_renderers CONT
                [[ "$last_action" == mute ]] && set_renderer_audio_mute 0
                [[ "$last_action" == running || "$last_action" == keep ]] || write_state running
                ;;
        esac
        last_action="$action"
        sleep 1
    done
}

restart_renderers() {
    stop_renderers

    if command -v systemd-run >/dev/null 2>&1 && systemctl --user is-system-running >/dev/null 2>&1; then
        systemd-run --user --quiet --collect --service-type=exec \
            --unit="$UNIT_PREFIX-$(date +%s%N)" "$SCRIPT_DIR/runtime.sh" run
    else
        setsid -f "$SCRIPT_DIR/runtime.sh" run
    fi
}

case "${1:-restart}" in
    restart|restore)
        restart_renderers
        ;;
    stop)
        stop_renderers
        ;;
    pause)
        pause_renderers
        ;;
    resume)
        resume_renderers
        ;;
    run)
        run_renderers
        ;;
    *)
        printf 'Usage: %s [restart|restore|stop|pause|resume|run]\n' "$0" >&2
        exit 2
        ;;
esac
