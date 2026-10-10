"""Verify live web gain and renderer ownership through actual Pulse streams."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--monitors', nargs=2, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    sink = f'lwe_volume_{os.getpid()}'
    module = subprocess.check_output(['pactl', 'load-module', 'module-null-sink', f'sink_name={sink}'], text=True).strip()
    processes = []
    logs = []
    try:
        with tempfile.TemporaryDirectory(prefix='lwe-web-volume-') as directory:
            root = Path(directory)
            (root / 'project.json').write_text(json.dumps({'title': 'Web Volume', 'type': 'web',
                                                         'file': 'index.html', 'workshopid': '987654321'}))
            (root / 'index.html').write_text('''<!doctype html><script>
const context = new AudioContext();
const oscillator = context.createOscillator();
const gain = context.createGain(); gain.gain.value = .03;
oscillator.connect(gain); gain.connect(context.destination);
oscillator.start(); context.resume();
</script>''')
            env = dict(os.environ, LD_LIBRARY_PATH=str(binary.parent), PULSE_SINK=sink,
                       __GL_THREADED_OPTIMIZATIONS='0')
            env.pop('__GLX_VENDOR_LIBRARY_NAME', None)
            env.pop('EGL_PLATFORM', None)
            def streams():
                return json.loads(subprocess.check_output(['pactl', '-f', 'json', 'list', 'sink-inputs'], text=True))
            def session(pid):
                if not str(pid).isdigit(): return None
                try:
                    return int(Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()[3])
                except (OSError, ValueError, IndexError):
                    return None
            def owned(index):
                return [s for s in streams() if session(s['properties'].get('application.process.id', ''))
                        == processes[index].pid]
            def wait(predicate, message):
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    assert all(p.poll() is None for p in processes), [(root / f'{i}.log').read_text() for i in range(len(processes))]
                    if predicate(): return
                    time.sleep(.1)
                raise AssertionError(message)
            def gains(index):
                return [((v['value'] / 65536) ** 3) for s in owned(index) for v in s['volume'].values()]
            for i, monitor in enumerate(args.monitors):
                log = (root / f'{i}.log').open('w')
                logs.append(log)
                processes.append(subprocess.Popen([str(binary), '--fps', '30', '--volume', '0', '--noautomute',
                    '--no-fullscreen-pause', '--anti-aliasing', '2', '--layer', 'background', '--screen-root', monitor,
                    '--assets-dir', str(args.assets), '--control-file', str(root / f'{i}.json'), str(root)],
                    env=env, stdout=log, stderr=log, start_new_session=True))
                wait(lambda: bool(owned(i)), 'missing renderer audio stream')
                # EasyEffects can reroute streams despite PULSE_SINK. Move only
                # this disposable renderer's streams before unmuting them.
                for stream in owned(i):
                    subprocess.run(['pactl', 'move-sink-input', str(stream['index']), sink], check=True)
            wait(lambda: all(gains(i) and max(gains(i)) < .0001 for i in range(2)), 'muted startup gain')
            for gain in [64, 32, 128, 0]:
                (root / '0.json').write_text(json.dumps({'volume': gain}))
                wait(lambda: gains(0) and all(abs(v - gain / 128) < .003 for v in gains(0)), 'live fractional gain')
                if gain:
                    wait(lambda: any(s['properties'].get('media.name') == 'Playback' for s in owned(0)),
                         'missing active CEF stream')
                assert max(gains(1)) < .0001, 'gain leaked to second renderer'
                print('PASS web live gain', gain, 'and monitor isolation', flush=True)
            # Reverse the ownership check: a change on monitor 2 must not alter 1.
            (root / '1.json').write_text(json.dumps({'volume': 16}))
            wait(lambda: gains(1) and all(abs(v - .125) < .003 for v in gains(1)), 'second monitor gain')
            assert max(gains(0)) < .0001
            print('PASS independent second monitor gain', flush=True)
    finally:
        for process in processes:
            if process.poll() is None: process.terminate()
        for process in processes:
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        for log in logs: log.close()
        subprocess.run(['pactl', 'unload-module', module], check=True)
        assert all(p.returncode == 0 for p in processes)


if __name__ == '__main__':
    main()
