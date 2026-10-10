"""Verify actual CEF audio ownership and session signals on a silent test sink."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import tempfile
import time
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--monitors', nargs=2, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    runtime = Path(__file__).resolve().parents[2] / 'dots/.config/quickshell/ii/scripts/wallpaperEngine/runtime.sh'
    sink = f'lwe_regression_{os.getpid()}'
    module = subprocess.check_output(['pactl', 'load-module', 'module-null-sink', f'sink_name={sink}'], text=True).strip()
    processes = []
    logs = []
    other = None
    try:
        with tempfile.TemporaryDirectory(prefix='lwe-audio-regression-') as directory:
            root = Path(directory)
            (root / 'project.json').write_text(json.dumps({'title': 'Audio Regression', 'type': 'web',
                                                         'file': 'index.html', 'workshopid': '987654321'}))
            (root / 'index.html').write_text('''<!doctype html><body><script>
const context = new AudioContext();
const oscillator = context.createOscillator();
const gain = context.createGain();
gain.gain.value = .03;
oscillator.connect(gain); gain.connect(context.destination);
oscillator.start(); context.resume();
</script></body>''')
            sinks = json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sinks'], text=True))
            sink_index = next(s['index'] for s in sinks if s['name'] == sink)
            env = dict(os.environ, __GL_THREADED_OPTIMIZATIONS='0', LD_LIBRARY_PATH=str(binary.parent), PULSE_SINK=sink)
            env.pop('__GLX_VENDOR_LIBRARY_NAME', None)
            env.pop('EGL_PLATFORM', None)
            for i, monitor in enumerate(args.monitors):
                name = f'linux-wallpaperengine:{monitor}'
                renderer_env = dict(env, SDL_AUDIO_DEVICE_APP_NAME=name, SDL_AUDIO_DEVICE_STREAM_NAME=name,
                                    PULSE_PROP=f'application.name={name} media.name={name}')
                log = (root / f'{i}.log').open('w')
                logs.append(log)
                processes.append(subprocess.Popen([str(binary), '--fps', '30', '--volume', '15', '--noautomute',
                    '--no-fullscreen-pause', '--anti-aliasing', '2', '--layer', 'background', '--screen-root', monitor,
                    '--assets-dir', str(args.assets), str(root)], env=renderer_env, stdout=log, stderr=log,
                    start_new_session=True))
            helper = root / 'helper.sh'
            helper.write_text(runtime.read_text().split('case "${1:-restart}" in')[0] + r'''
renderer_pids["$TEST_MONITOR0"]="$TEST_PID0"
renderer_pids["$TEST_MONITOR1"]="$TEST_PID1"
# Isolate audio detection from any music the user is currently playing.
pactl() {
    if [[ "$*" == '-f json list sink-inputs' ]]; then
        command pactl "$@" | jq --argjson sink "$TEST_SINK_ID" 'map(select(.sink == $sink))'
    else
        command pactl "$@"
    fi
}
case "$1" in
    other) other_audio_playing ;;
    mute) set_renderer_audio_mute "$2" "$3" ;;
    signal) signal_renderer "$2" "$3" ;;
esac
''')
            helper_env = dict(env, TEST_MONITOR0=args.monitors[0], TEST_MONITOR1=args.monitors[1],
                              TEST_PID0=str(processes[0].pid), TEST_PID1=str(processes[1].pid), TEST_SINK_ID=str(sink_index))

            def run_helper(*command):
                return subprocess.run(['bash', str(helper), *command], env=helper_env, check=False).returncode

            def streams():
                result = json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sink-inputs'], text=True))
                return [s for s in result if s['sink'] == sink_index]

            def wait_for(predicate, message, timeout=35):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    assert all(p.poll() is None for p in processes), [(root / f'{i}.log').read_text() for i in range(2)]
                    if predicate(): return
                    time.sleep(.2)
                raise AssertionError(message)

            def session(pid):
                return int(Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()[3])

            wait_for(lambda: all(any(session(int(s['properties']['application.process.id'])) == p.pid
                                     for s in streams()) for p in processes), 'web audio streams missing')
            # PipeWire can restore the shared Chromium stream's previous mute state.
            # Establish both baselines before measuring monitor isolation.
            for monitor in args.monitors:
                assert run_helper('mute', monitor, '0') == 0
            wait_for(lambda: all(not s['mute'] for s in streams()), 'unmuted audio baseline')
            assert run_helper('other') == 1, 'wallpaper audio detected as another app'
            assert run_helper('mute', args.monitors[0], '1') == 0
            owned = [s for s in streams() if session(int(s['properties']['application.process.id'])) == processes[0].pid]
            assert owned and all(s['mute'] for s in owned), 'first monitor was not muted'
            owned = [s for s in streams() if session(int(s['properties']['application.process.id'])) == processes[1].pid]
            assert owned and all(not s['mute'] for s in owned), 'individual mute leaked to second monitor'
            assert run_helper('mute', args.monitors[0], '0') == 0
            print('PASS CEF self-audio exclusion and individual monitor mute', flush=True)

            for sig, paused in [('STOP', True), ('CONT', False)]:
                assert run_helper('signal', args.monitors[0], sig) == 0
                time.sleep(.2)
                children = [p for p in Path('/proc').iterdir() if p.name.isdigit()]
                owned = []
                for child in children:
                    try:
                        parts = (child / 'stat').read_text().rsplit(') ', 1)[1].split()
                        if int(parts[3]) == processes[0].pid and parts[0] != 'Z': owned.append(parts[0])
                    except (FileNotFoundError, ProcessLookupError): pass
                assert owned and all((state == 'T') == paused for state in owned), (sig, owned)
                assert Path(f'/proc/{processes[1].pid}/stat').read_text().rsplit(') ',1)[1][0] != 'T'
            print('PASS session pause/resume includes Chromium children on one monitor', flush=True)

            with wave.open(str(root / 'tone.wav'), 'w') as wav:
                wav.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
                second = b''.join(struct.pack('<h', int(2000 * math.sin(i * 2 * math.pi * 440 / 44100))) for i in range(44100))
                wav.writeframes(second * 30)
            other_env = dict(env)
            other_env.pop('PULSE_PROP', None)
            other = subprocess.Popen(['paplay', '--client-name=lwe-other-app', str(root / 'tone.wav')], env=other_env)
            wait_for(lambda: run_helper('other') == 0, 'other-app audio was not detected')
            for monitor in args.monitors:
                assert run_helper('mute', monitor, '1') == 0
            wallpaper_streams = [s for s in streams() if s['properties'].get('application.process.binary') == 'linux-wallpaperengine']
            assert len(wallpaper_streams) >= 2 and all(s['mute'] for s in wallpaper_streams)
            print('PASS global other-app audio detection and mute', flush=True)
    finally:
        if other and other.poll() is None:
            other.terminate()
            other.wait(timeout=5)
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGCONT)
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        for log in logs: log.close()
        subprocess.run(['pactl', 'unload-module', module], check=True)
        assert all(p.returncode == 0 for p in processes), [p.returncode for p in processes]


if __name__ == '__main__':
    main()
