"""Exercise the real supervisor with isolated config and disposable processes."""
from pathlib import Path
import json
import os
import signal
import subprocess
import tempfile
import time

runtime = Path(__file__).resolve().parents[2] / 'dots/.config/quickshell/ii/scripts/wallpaperEngine/runtime.sh'

def run(live):
    with tempfile.TemporaryDirectory(prefix='lwe-supervisor-') as directory:
        root = Path(directory)
        config = root / 'config.json'
        monitors = root / 'monitors.json'
        clients = root / 'clients.json'
        audio = root / 'audio'
        engine = root / 'engine'
        helper = root / 'helper.py'
        engine.write_text('''#!/bin/bash
if [[ "$1" == --help ]]; then
    [[ "$TEST_LIVE" == true ]] && echo '--control-file --input-file'
    exit 0
fi
printf '%s\\n' "$BASHPID $*" >> "$TEST_DIR/starts"
printf '%s\\n' "${__EGL_VENDOR_LIBRARY_FILENAMES:-unset}" >> "$TEST_DIR/egl-vendors"
sleep 10000 &
child=$!
printf '%s\\n' "$BASHPID $child" >> "$TEST_DIR/children"
trap 'wait "$child"; exit 0' TERM INT
while true; do sleep 0.1; done
''')
        engine.chmod(0o755)
        helper.write_text("print('/assets')\n")
        data = {'background': {'wallpaperEngine': {'muted': False, 'fps': 30, 'volume': 15,
            'behavior': {'fullscreen': 'pause', 'maximized': 'pause', 'audioPlaying': 'mute',
                         'fullscreenOnlyActive': False}}, 'wallpapersByMonitor': [
                {'monitor': 'HDMI-A-1', 'path': '/wallpaper/a', 'type': 'wallpaper-engine'},
                {'monitor': 'eDP-1', 'path': '/wallpaper/b', 'type': 'wallpaper-engine'}]}}
        screens = [{'name': 'HDMI-A-1', 'activeWorkspace': {'id': 3}},
                   {'name': 'eDP-1', 'activeWorkspace': {'id': 1}}]
        def save(path, value):
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(value))
            temporary.replace(path)
        save(config, data)
        save(monitors, screens)
        save(clients, [])
        audio.write_text('false')
        script = root / 'supervisor.sh'
        script.write_text(runtime.read_text().split('case "${1:-restart}" in')[0] + r'''
CONFIG_FILE="$TEST_DIR/config.json"
LOG_DIR="$TEST_DIR/log"
STATE_FILE="$LOG_DIR/state"
MONITOR_STATE_FILE="$LOG_DIR/states.json"
HELPER="$TEST_DIR/helper.py"
find_engine() { printf '%s\n' "$TEST_DIR/engine"; }
hyprctl() { cat "$TEST_DIR/$1.json"; }
other_audio_playing() { [[ "$(cat "$TEST_DIR/audio")" == true ]]; }
set_renderer_audio_mute() { printf '%s\n' "$1 $2" >> "$TEST_DIR/mutes"; }
run_renderers
''')
        env = dict(os.environ, TEST_DIR=directory, TEST_LIVE=str(live).lower(),
                   AQ_DRM_DEVICES='/dev/dri/nvidia-gpu:/dev/dri/intel-igpu')
        if live:
            env['__EGL_VENDOR_LIBRARY_FILENAMES'] = '/test/explicit-egl-vendor.json'
        else:
            env.pop('__EGL_VENDOR_LIBRARY_FILENAMES', None)
        log = (root / 'supervisor.log').open('w')
        process = subprocess.Popen(['bash', str(script)], env=env, stdout=log, stderr=log)
        seen = set()
        def starts():
            path = root / 'starts'
            if not path.exists(): return {}
            result = {}
            for line in path.read_text().splitlines():
                words = line.split()
                pid = int(words[0])
                seen.add(pid)
                result[words[words.index('--screen-root') + 1]] = pid
            return result
        def state(pid):
            try: return Path(f'/proc/{pid}/stat').read_text().split()[2]
            except FileNotFoundError: return None
        def children():
            path = root / 'children'
            if not path.exists(): return {}
            return {int(line.split()[0]): int(line.split()[1]) for line in path.read_text().splitlines()}
        def until(predicate, message, timeout=12):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                assert process.poll() is None, (message, (root / 'supervisor.log').read_text())
                if predicate(): return
                time.sleep(.1)
            raise AssertionError((message, (root / 'supervisor.log').read_text()))
        try:
            until(lambda: len(starts()) == 2, 'initial outputs')
            initial = starts()
            lines = (root / 'starts').read_text().splitlines()
            if live:
                input_paths = [Path(line.split()[line.split().index('--input-file') + 1]) for line in lines]
                assert len(set(input_paths)) == 2, input_paths
                assert all(json.loads(path.read_text())['leftDown'] is False for path in input_paths)
                assert all('--control-file' in line for line in lines), lines
            else:
                assert all('--input-file' not in line for line in lines), lines
            time.sleep(4)
            vendors = (root / 'egl-vendors').read_text().splitlines()
            expected_vendor = '/test/explicit-egl-vendor.json' if live else 'unset'
            assert vendors == [expected_vendor, expected_vendor], vendors
            data['background']['wallpaperEngine'].update(fps=60, volume=25)
            save(config, data)
            if live:
                control = root / 'log/control-HDMI-A-1.json'
                until(lambda: control.exists() and json.loads(control.read_text())['fps'] == 60, 'live update')
                assert starts() == initial, 'live settings restarted processes'
            else:
                until(lambda: all(starts()[name] != pid for name, pid in initial.items()), 'legacy restart')
            initial = starts()
            data['background']['wallpapersByMonitor'][0]['properties'] = {'test': 1}
            save(config, data)
            until(lambda: starts()['HDMI-A-1'] != initial['HDMI-A-1'], 'affected resource restart')
            assert starts()['eDP-1'] == initial['eDP-1'], 'unaffected output restarted'
            initial = starts()
            save(clients, [{'workspace': {'id': 3}, 'floating': False, 'fullscreen': 0}])
            until(lambda: state(initial['HDMI-A-1']) == 'T', 'tiled output pause')
            assert state(initial['eDP-1']) != 'T', 'tiled policy leaked to other output'
            assert state(children()[initial['HDMI-A-1']]) == 'T', 'renderer child was not paused'
            assert state(children()[initial['eDP-1']]) != 'T', 'child policy leaked to other output'
            screens[0]['activeWorkspace']['id'] = 4
            save(monitors, screens)
            until(lambda: state(initial['HDMI-A-1']) != 'T', 'workspace resume')
            save(clients, [{'workspace': {'id': 1}, 'floating': True, 'fullscreen': 2}])
            until(lambda: state(initial['eDP-1']) == 'T', 'fullscreen output pause')
            assert state(initial['HDMI-A-1']) != 'T', 'fullscreen policy leaked to other output'
            save(clients, [])
            until(lambda: state(initial['eDP-1']) != 'T', 'fullscreen resume')
            data['background']['wallpapersByMonitor'][0]['muted'] = True
            save(config, data)
            if live:
                until(lambda: json.loads(control.read_text())['volume'] == 0, 'individual mute')
                assert starts() == initial, 'individual live mute restarted renderer'
                assert json.loads((root / 'log/control-eDP-1.json').read_text())['volume'] == 25
            else:
                until(lambda: starts()['HDMI-A-1'] != initial['HDMI-A-1'], 'legacy individual mute')
                assert starts()['eDP-1'] == initial['eDP-1'], 'individual mute restarted other output'
            data['background']['wallpapersByMonitor'][0]['muted'] = False
            save(config, data)
            muted_pid = starts()['HDMI-A-1']
            if live:
                until(lambda: json.loads(control.read_text())['volume'] == 25, 'live individual unmute')
            else:
                until(lambda: starts()['HDMI-A-1'] != muted_pid, 'legacy individual unmute')
            until(lambda: (root / 'log/state').read_text().strip() == 'running', 'individual unmute')
            initial = starts()
            audio.write_text('true')
            until(lambda: (root / 'log/state').read_text().strip() == 'muted', 'global audio mute')
            mutes = (root / 'mutes').read_text()
            assert 'HDMI-A-1 1' in mutes and 'eDP-1 1' in mutes
            audio.write_text('false')
            data['background']['wallpaperEngine']['paused'] = True
            save(config, data)
            until(lambda: all(state(pid) == 'T' for pid in initial.values()), 'manual pause')
            data['background']['wallpaperEngine']['paused'] = False
            save(config, data)
            until(lambda: all(state(pid) != 'T' for pid in initial.values()), 'manual resume')
            os.kill(initial['HDMI-A-1'], signal.SIGKILL)
            until(lambda: starts()['HDMI-A-1'] != initial['HDMI-A-1'], 'crash recovery')
            initial = starts()
            save(monitors, screens[1:])
            until(lambda: state(initial['HDMI-A-1']) is None, 'disconnect cleanup')
            assert starts()['eDP-1'] == initial['eDP-1']
            save(monitors, screens)
            until(lambda: starts()['HDMI-A-1'] != initial['HDMI-A-1'], 'reconnect startup')
            initial = starts()
            data['background']['wallpaperEngine']['behavior']['maximized'] = 'stop'
            save(config, data)
            save(clients, [{'workspace': {'id': 4}, 'floating': False, 'fullscreen': 0}])
            until(lambda: state(initial['HDMI-A-1']) is None, 'tiled stop')
            data['background']['wallpapersByMonitor'][0]['properties'] = {'test': 2}
            save(config, data)
            until(lambda: starts()['HDMI-A-1'] != initial['HDMI-A-1'], 'config reload while stopped')
            reloaded = starts()['HDMI-A-1']
            assert state(reloaded) not in (None, 'T'), 'startup rendering was skipped under stop policy'
            time.sleep(1)
            assert state(reloaded) not in (None, 'T'), 'startup grace ended too soon'
            until(lambda: state(reloaded) is None, 'stop policy after startup grace')
            assert starts()['eDP-1'] == initial['eDP-1'], 'stop policy changed other output'
            save(clients, [])
            until(lambda: starts()['HDMI-A-1'] != reloaded, 'resume from stop')
            data['background']['wallpapersByMonitor'][0].update(type='image', path='/image.png')
            old = starts()['HDMI-A-1']
            save(config, data)
            until(lambda: state(old) is None, 'static image releases renderer')
        finally:
            process.terminate()
            process.wait(timeout=10)
            log.close()
            assert all(state(pid) is None for pid in seen), 'supervisor leaked child processes'
            assert all(state(pid) in (None, 'Z') for pid in children().values()), 'supervisor leaked renderer descendants'
        print('PASS supervisor', 'live' if live else 'legacy', flush=True)

run(True)
run(False)
