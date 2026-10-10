#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(cd -- "$(dirname -- "$0")/../.." && pwd)
fixture_dir="$repo_dir/tests/quickshell-widget-profiles"
shell_dir="$repo_dir/dots/.config/quickshell/ii"
test_dir=$(mktemp -d)
trap 'rm -rf -- "$test_dir"' EXIT
mkdir -p "$test_dir/config/illogical-impulse"
for entry in modules services GlobalStates.qml scripts assets translations; do
    ln -s "$shell_dir/$entry" "$test_dir/$entry"
done
cp "$fixture_dir/"*.qml "$test_dir/"
cat > "$test_dir/config/illogical-impulse/config.json" <<'JSON'
{"background":{"widgetsLocked":true,"widgets":{"clock":{"x":321,"style":"digital","digital":{"font":{"size":73}}},"weather":{"enable":true,"sizeMode":"1x2"},"worldClock":{"timezones":["Asia/Tokyo","Europe/London"]}}}}
JSON
export XDG_CONFIG_HOME="$test_dir/config"
export XDG_CACHE_HOME="$test_dir/cache"
export XDG_STATE_HOME="$test_dir/state"
for phase in shell restart components; do
    timeout 15 qs --no-color -p "$test_dir/$phase.qml" > "$test_dir/$phase.log" 2>&1
    cat "$test_dir/$phase.log"
    case "$phase" in
        shell) marker='PROFILE TEST PASS' ;;
        restart) marker='RESTART TEST PASS' ;;
        components) marker='COMPONENT TEST PASS' ;;
    esac
    rg -q "$marker" "$test_dir/$phase.log"
done
