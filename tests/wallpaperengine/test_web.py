"""Verify CEF sees each output's real viewport at startup and exits cleanly."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--monitors', nargs=2, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    monitors = json.loads(subprocess.check_output(['hyprctl', 'monitors', '-j'], text=True))
    sizes = {m['name']: (round(m['width'] / m['scale']) * round(m['scale']),
                         round(m['height'] / m['scale']) * round(m['scale'])) for m in monitors}
    env = dict(os.environ, LD_LIBRARY_PATH=str(binary.parent), __GL_THREADED_OPTIMIZATIONS='0')
    env.pop('__GLX_VENDOR_LIBRARY_NAME', None)
    env.pop('EGL_PLATFORM', None)
    with tempfile.TemporaryDirectory(prefix='lwe-web-regression-') as directory:
        root = Path(directory)
        (root / 'project.json').write_text(json.dumps({'title': 'Viewport Regression', 'type': 'web',
                                                     'file': 'index.html', 'workshopid': '987654321'}))
        for monitor in args.monitors:
            width, height = sizes[monitor]
            # Capture startup size before any subsequent resize notification can repair it.
            (root / 'index.html').write_text('''<!doctype html><style>
html,body{margin:0;width:100%%;height:100%%}</style><script>
const correct = innerWidth === %d && innerHeight === %d;
document.documentElement.style.background = correct ? '#12cd34' : '#ed1234';
</script>''' % (width, height))
            capture = root / 'capture.png'
            capture.unlink(missing_ok=True)
            with (root / 'renderer.log').open('w') as log:
                process = subprocess.Popen([str(binary), '--fps', '30', '--silent', '--noautomute',
                    '--no-fullscreen-pause', '--anti-aliasing', '2', '--layer', 'background',
                    '--screen-root', monitor, '--assets-dir', str(args.assets),
                    '--screenshot', str(capture), '--screenshot-delay', '100', str(root)],
                    env=env, stdout=log, stderr=log, start_new_session=True)
                try:
                    deadline = time.monotonic() + 35
                    while not capture.exists() and time.monotonic() < deadline:
                        assert process.poll() is None, (root / 'renderer.log').read_text()
                        time.sleep(.1)
                    assert capture.exists(), (root / 'renderer.log').read_text()
                    time.sleep(.2)
                    with Image.open(capture) as image:
                        assert image.size == (width, height), (monitor, image.size, (width, height))
                        assert image.convert('RGB').getpixel((width // 2, height // 2)) == (18, 205, 52)
                finally:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise
                assert process.returncode == 0, (root / 'renderer.log').read_text()
            print('PASS web startup viewport and clean shutdown', monitor, flush=True)


if __name__ == '__main__':
    main()
