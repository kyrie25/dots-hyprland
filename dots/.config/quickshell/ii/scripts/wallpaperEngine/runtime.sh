#!/usr/bin/env bash

set -u

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
CONFIG_FILE="$XDG_CONFIG_HOME/illogical-impulse/config.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER="$SCRIPT_DIR/wallpaper-engine.py"
LOG_DIR="$XDG_CACHE_HOME/linux-wallpaperengine"
VIDEO_OPTS="no-audio loop hwdec=auto scale=bilinear interpolation=no video-sync=display-resample panscan=1.0 video-scale-x=1.0 video-scale-y=1.0 video-align-x=0.5 video-align-y=0.5 load-scripts=no"
UNIT_PREFIX="illogical-impulse-wallpaper"
ENGINE_PATTERN='^(\./|/[^ ]*/)?linux-wallpaperengine( |$)'

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
            return
        fi
        sleep 0.05
    done
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

run_renderers() {
    [[ -f "$CONFIG_FILE" ]] || return 0

    local engine=""
    local assets=""
    engine="$(find_engine 2>/dev/null || true)"
    assets="$(python3 "$HELPER" locate assets 2>/dev/null || true)"
    mkdir -p "$LOG_DIR"

    local -a engine_args=()
    local -a renderer_pids=()
    local first_engine_path=""
    local monitor path type configured_type
    while IFS= read -r monitor; do
        [[ -n "$monitor" ]] || continue
        path="$(jq -r --arg monitor "$monitor" '
            ((.background.wallpapersByMonitor // []) | map(select(.monitor == $monitor)) | .[0].path)
            // .background.wallpaperPath // ""
        ' "$CONFIG_FILE")"
        configured_type="$(jq -r --arg monitor "$monitor" '
            ((.background.wallpapersByMonitor // []) | map(select(.monitor == $monitor)) | .[0].type)
            // .background.wallpaperType // "auto"
        ' "$CONFIG_FILE")"
        [[ -n "$path" && "$path" != "null" ]] || continue
        type="$(wallpaper_type "$path" "$configured_type")"

        case "$type" in
            wallpaper-engine)
                [[ -n "$engine" && -n "$assets" ]] || continue
                engine_args+=(--screen-root "$monitor" --bg "$path" --scaling fill)
                [[ -n "$first_engine_path" ]] || first_engine_path="$path"
                ;;
            video)
                command -v mpvpaper >/dev/null 2>&1 || continue
                mpvpaper -o "$VIDEO_OPTS" "$monitor" "$path" >"$LOG_DIR/mpvpaper-$monitor.log" 2>&1 &
                renderer_pids+=("$!")
                ;;
        esac
    done < <(hyprctl monitors -j | jq -r '.[].name')

    if [[ ${#engine_args[@]} -gt 0 ]]; then
        local -a engine_env=(__GL_THREADED_OPTIMIZATIONS=0)
        if [[ "${AQ_DRM_DEVICES:-}" == *nvidia*:*intel* ]]; then
            engine_env+=(DRI_PRIME=1 LIBVA_DRIVER_NAME=iHD)
        fi
        env -u __GLX_VENDOR_LIBRARY_NAME "${engine_env[@]}" "$engine" \
            --fps 30 --silent --fullscreen-pause-only-active --layer background \
            --assets-dir "$assets" "${engine_args[@]}" "$first_engine_path" \
            >"$LOG_DIR/runtime.log" 2>&1 &
        renderer_pids+=("$!")
    fi

    if [[ ${#renderer_pids[@]} -gt 0 ]]; then
        wait "${renderer_pids[@]}"
    fi
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
    run)
        run_renderers
        ;;
    *)
        printf 'Usage: %s [restart|restore|stop|run]\n' "$0" >&2
        exit 2
        ;;
esac
