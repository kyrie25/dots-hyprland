#!/usr/bin/env bash

set -u

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
CONFIG_FILE="$XDG_CONFIG_HOME/illogical-impulse/config.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER="$SCRIPT_DIR/wallpaper-engine.py"
LOG_DIR="$XDG_CACHE_HOME/linux-wallpaperengine"
STATE_FILE="$LOG_DIR/state"
MONITOR_STATE_FILE="$LOG_DIR/states.json"
STARTUP_GRACE_SECONDS=3
VIDEO_OPTS="no-audio loop hwdec=auto scale=bilinear interpolation=no video-sync=display-resample panscan=1.0 video-scale-x=1.0 video-scale-y=1.0 video-align-x=0.5 video-align-y=0.5 load-scripts=no"
UNIT_PREFIX="illogical-impulse-wallpaper"
ENGINE_PATTERN='^(\./|/[^ ]*/)?linux-wallpaperengine( |$)'
declare -A renderer_pids=()
declare -A configured_monitors=()
declare -A renderer_states=()
declare -A renderer_grace_deadlines=()

write_state() {
    mkdir -p "$LOG_DIR"
    printf '%s\n' "$1" >"$STATE_FILE.tmp"
    mv "$STATE_FILE.tmp" "$STATE_FILE"
}

write_empty_monitor_states() {
    mkdir -p "$LOG_DIR"
    printf '{}\n' >"$MONITOR_STATE_FILE.tmp"
    mv "$MONITOR_STATE_FILE.tmp" "$MONITOR_STATE_FILE"
}

write_monitor_states() {
    local aggregate=""
    local monitor state
    while IFS= read -r monitor; do
        [[ -n "$monitor" ]] || continue
        state="${renderer_states[$monitor]:-stopped}"
        if [[ -z "$aggregate" ]]; then
            aggregate="$state"
        elif [[ "$aggregate" != "$state" ]]; then
            aggregate=mixed
        fi
    done < <(printf '%s\n' "${!configured_monitors[@]}" | sort)

    {
        while IFS= read -r monitor; do
            [[ -n "$monitor" ]] || continue
            printf '%s\t%s\n' "$monitor" "${renderer_states[$monitor]:-stopped}"
        done < <(printf '%s\n' "${!configured_monitors[@]}" | sort)
    } | jq -Rn '
        reduce inputs as $line ({};
            ($line | split("\t")) as $entry
            | .[$entry[0]] = $entry[1]
        )
    ' >"$MONITOR_STATE_FILE.tmp"
    mv "$MONITOR_STATE_FILE.tmp" "$MONITOR_STATE_FILE"
    write_state "${aggregate:-stopped}"
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
            write_empty_monitor_states
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
    local -a pids=("${renderer_pids[@]}")
    kill -CONT "${pids[@]}" 2>/dev/null || true
    kill -TERM "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
    renderer_pids=()
    renderer_grace_deadlines=()
}

stop_renderer() {
    local monitor="$1"
    local pid="${renderer_pids[$monitor]:-}"
    [[ -n "$pid" ]] || return
    kill -CONT "$pid" 2>/dev/null || true
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    unset 'renderer_pids[$monitor]'
    unset 'renderer_grace_deadlines[$monitor]'
}

renderer_alive() {
    local monitor="$1"
    local pid="${renderer_pids[$monitor]:-}"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

signal_renderer() {
    local monitor="$1"
    local signal="$2"
    local pid="${renderer_pids[$monitor]:-}"
    [[ -n "$pid" ]] && kill "-$signal" "$pid" 2>/dev/null || true
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

    local only_monitor="${1:-}"
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

    local started=false
    local monitor entry path type configured_type scaling align_x align_y properties safe_monitor
    while IFS= read -r monitor; do
        [[ -n "$monitor" ]] || continue
        [[ -z "$only_monitor" || "$monitor" == "$only_monitor" ]] || continue
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
                local -a overrides=()
                mapfile -d '' -t overrides < <(property_args "$properties")
                local -a engine_env=(
                    __GL_THREADED_OPTIMIZATIONS=0
                    SDL_AUDIO_DEVICE_APP_NAME="linux-wallpaperengine:$monitor"
                    SDL_AUDIO_DEVICE_STREAM_NAME="linux-wallpaperengine:$monitor"
                )
                if [[ "${AQ_DRM_DEVICES:-}" == *nvidia*:*intel* ]]; then
                    engine_env+=(DRI_PRIME=1 LIBVA_DRIVER_NAME=iHD)
                fi
                safe_monitor="${monitor//[^A-Za-z0-9_.-]/_}"
                env -u __GLX_VENDOR_LIBRARY_NAME "${engine_env[@]}" "$engine" \
                    "${common_args[@]}" \
                    --screen-root "$monitor" \
                    --bg "$path" \
                    --scaling "$scaling" \
                    --align-x "$align_x" \
                    --align-y "$align_y" \
                    "${overrides[@]}" "$path" \
                    >"$LOG_DIR/runtime-$safe_monitor.log" 2>&1 &
                renderer_pids["$monitor"]="$!"
                configured_monitors["$monitor"]=1
                renderer_states["$monitor"]=running
                renderer_grace_deadlines["$monitor"]=$((SECONDS + STARTUP_GRACE_SECONDS))
                started=true
                ;;
            video)
                command -v mpvpaper >/dev/null 2>&1 || continue
                mpvpaper -o "$VIDEO_OPTS" "$monitor" "$path" >"$LOG_DIR/mpvpaper-$monitor.log" 2>&1 &
                renderer_pids["$monitor"]="$!"
                configured_monitors["$monitor"]=1
                renderer_states["$monitor"]=running
                renderer_grace_deadlines["$monitor"]=$((SECONDS + STARTUP_GRACE_SECONDS))
                started=true
                ;;
        esac
    done < <(hyprctl monitors -j | jq -r '.[].name')

    [[ "$started" == true ]]
}

other_audio_playing() {
    command -v pactl >/dev/null 2>&1 || return 1
    pactl -f json list sink-inputs 2>/dev/null | jq -e '
        any(.[];
            (.corked == false)
            and (.mute != true)
            and ((.properties."application.name" // "") | startswith("linux-wallpaperengine") | not)
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
        $monitors[] as $monitor
        | [
            $monitor.name,
            any($clients[];
                (.hidden != true)
                and (.workspace.id == $monitor.activeWorkspace.id)
                and (((.fullscreen // 0) == 2) or ((.fullscreen // 0) == 3))
                and (($activeOnly | not) or ((.focusHistoryID // -1) == 0))
            ),
            any($clients[];
                (.hidden != true)
                and (.workspace.id == $monitor.activeWorkspace.id)
                and (.floating == false)
                and (((.fullscreen // 0) == 0) or ((.fullscreen // 0) == 1))
            )
        ]
        | @tsv
    '
}

desired_action() {
    local fullscreen="$1"
    local maximized="$2"
    local audio_playing="$3"
    local manual_pause="$4"
    local fullscreen_action="$5"
    local maximized_action="$6"
    local audio_action="$7"
    local allow_suspend="${8:-true}"
    if [[ "$allow_suspend" != true ]]; then
        [[ "$fullscreen_action" == pause || "$fullscreen_action" == stop ]] && fullscreen_action=keep
        [[ "$maximized_action" == pause || "$maximized_action" == stop ]] && maximized_action=keep
        [[ "$audio_action" == pause || "$audio_action" == stop ]] && audio_action=keep
        manual_pause=false
    fi
    local -a actions=()
    [[ "$fullscreen" == true ]] && actions+=("$fullscreen_action")
    [[ "$maximized" == true ]] && actions+=("$maximized_action")
    [[ "$audio_playing" == true ]] && actions+=("$audio_action")
    [[ "$manual_pause" == true ]] && actions+=(pause)

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
    local monitor="$1"
    local muted="$2"
    command -v pactl >/dev/null 2>&1 || return
    local index
    while IFS= read -r index; do
        [[ -n "$index" ]] && pactl set-sink-input-mute "$index" "$muted" >/dev/null 2>&1 || true
    done < <(pactl -f json list sink-inputs 2>/dev/null | jq -r --arg stream "linux-wallpaperengine:$monitor" '
        .[]
        | select((.properties."application.name" // "") | startswith("linux-wallpaperengine"))
        | select((.properties."media.name" // "") == $stream)
        | .index
    ')
}

run_renderers() {
    [[ -f "$CONFIG_FILE" ]] || return 0
    mkdir -p "$LOG_DIR"
    trap 'stop_children; write_state stopped; write_empty_monitor_states' EXIT
    trap 'exit 0' INT TERM

    start_renderers || {
        write_state stopped
        write_empty_monitor_states
        return 0
    }
    write_monitor_states

    local -A last_actions=()
    while true; do
        local settings fullscreen_action maximized_action audio_action manual_pause
        settings="$(jq -c '.background.wallpaperEngine // {}' "$CONFIG_FILE")"
        fullscreen_action="$(jq -r '.behavior.fullscreen // "pause"' <<<"$settings")"
        maximized_action="$(jq -r '.behavior.maximized // "keep"' <<<"$settings")"
        audio_action="$(jq -r '.behavior.audioPlaying // "keep"' <<<"$settings")"
        manual_pause="$(jq -r '.paused // false' <<<"$settings")"

        local audio_playing=false
        other_audio_playing && audio_playing=true

        local -A fullscreen_by_monitor=()
        local -A maximized_by_monitor=()
        local state_monitor fullscreen maximized
        while IFS=$'\t' read -r state_monitor fullscreen maximized; do
            [[ -n "$state_monitor" ]] || continue
            fullscreen_by_monitor["$state_monitor"]="$fullscreen"
            maximized_by_monitor["$state_monitor"]="$maximized"
        done < <(window_states)

        local monitor raw_action action last_action allow_suspend deadline
        while IFS= read -r monitor; do
            [[ -n "$monitor" ]] || continue
            raw_action="$(desired_action \
                "${fullscreen_by_monitor[$monitor]:-false}" \
                "${maximized_by_monitor[$monitor]:-false}" \
                "$audio_playing" "$manual_pause" \
                "$fullscreen_action" "$maximized_action" "$audio_action" true)"
            last_action="${last_actions[$monitor]:-}"

            if [[ "$raw_action" != stop ]] && ! renderer_alive "$monitor"; then
                stop_renderer "$monitor"
                if ! start_renderers "$monitor"; then
                    renderer_states["$monitor"]=stopped
                    last_actions["$monitor"]=stop
                    continue
                fi
                last_action=""
            fi

            allow_suspend=true
            deadline="${renderer_grace_deadlines[$monitor]:-0}"
            if renderer_alive "$monitor" && ((SECONDS < deadline)); then
                allow_suspend=false
            fi
            action="$(desired_action \
                "${fullscreen_by_monitor[$monitor]:-false}" \
                "${maximized_by_monitor[$monitor]:-false}" \
                "$audio_playing" "$manual_pause" \
                "$fullscreen_action" "$maximized_action" "$audio_action" "$allow_suspend")"

            case "$action" in
                stop)
                    [[ "$last_action" == stop ]] || stop_renderer "$monitor"
                    renderer_states["$monitor"]=stopped
                    ;;
                pause)
                    if [[ "$last_action" != pause ]]; then
                        [[ "$last_action" == mute ]] && set_renderer_audio_mute "$monitor" 0
                        signal_renderer "$monitor" STOP
                    fi
                    renderer_states["$monitor"]=paused
                    ;;
                mute)
                    [[ "$last_action" == pause ]] && signal_renderer "$monitor" CONT
                    set_renderer_audio_mute "$monitor" 1
                    renderer_states["$monitor"]=muted
                    ;;
                keep|*)
                    [[ "$last_action" == pause ]] && signal_renderer "$monitor" CONT
                    [[ "$last_action" == mute ]] && set_renderer_audio_mute "$monitor" 0
                    renderer_states["$monitor"]=running
                    ;;
            esac
            last_actions["$monitor"]="$action"
        done < <(printf '%s\n' "${!configured_monitors[@]}" | sort)
        write_monitor_states
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
