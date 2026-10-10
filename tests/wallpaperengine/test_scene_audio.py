"""Test mono/stereo scene decoding and live volume using SDL disk output."""
import argparse
import array
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
    parser.add_argument('--monitor', required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    with tempfile.TemporaryDirectory(prefix='lwe-scene-audio-') as directory:
        root = Path(directory)
        (root / 'project.json').write_text(json.dumps({'title': 'Scene Audio Regression',
                                                     'type': 'scene', 'file': 'scene.json'}))
        env = dict(os.environ, SDL_AUDIODRIVER='disk',
                   SDL_AUDIO_DISK_OUTPUT_FILE=str(root / 'capture.raw'),
                   SDL_DISKAUDIOFILE=str(root / 'capture.raw'),
                   LD_LIBRARY_PATH=str(binary.parent), __GL_THREADED_OPTIMIZATIONS='0')
        env.pop('__GLX_VENDOR_LIBRARY_NAME', None)
        env.pop('EGL_PLATFORM', None)

        def rms():
            time.sleep(.5)
            raw = (root / 'capture.raw').read_bytes()
            samples = array.array('f')
            samples.frombytes(raw[-48000 * 2 * 4 // 4:len(raw) // 4 * 4])
            assert samples, 'no samples captured'
            return math.sqrt(sum(s * s for s in samples) / len(samples))

        for channels, rate, count in [(1, 44100, 1), (2, 48000, 1), (1, 22050, 2)]:
            with wave.open(str(root / 'tone.wav'), 'w') as wav:
                wav.setparams((channels, 2, rate, 0, 'NONE', 'not compressed'))
                samples = b''.join(struct.pack('<h', int(3000 * math.sin(i * 2 * math.pi * 440 / rate)))
                                   * channels for i in range(rate))
                wav.writeframes(samples * 3)
            (root / 'scene.json').write_text(json.dumps({
                'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                'general': {'orthogonalprojection': {'width': 640, 'height': 480}},
                'objects': [{'id': i + 1, 'name': f'sound{i}', 'sound': ['tone.wav'],
                             'playbackmode': 'loop'} for i in range(count)]}))
            control = root / 'control.json'
            control.unlink(missing_ok=True)
            with (root / 'renderer.log').open('w') as log:
                process = subprocess.Popen([str(binary), '--fps', '30', '--volume', '0',
                    '--noautomute', '--no-fullscreen-pause', '--anti-aliasing', '2',
                    '--layer', 'background', '--screen-root', args.monitor,
                    '--assets-dir', str(args.assets), '--control-file', str(control), str(root)],
                    env=env, stdout=log, stderr=log, start_new_session=True)
                try:
                    time.sleep(2)
                    assert process.poll() is None, (root / 'renderer.log').read_text()
                    assert rms() < .00001, 'muted startup produced sound'
                    control.write_text(json.dumps({'volume': 64}))
                    time.sleep(1)
                    loud = rms()
                    assert loud > .01, f'live unmute produced no audio: {loud}'
                    # Cross the authored loop boundary, then mute and unmute again.
                    control.write_text(json.dumps({'volume': 0}))
                    time.sleep(1)
                    assert rms() < .00001, 'live mute produced sound'
                    control.write_text(json.dumps({'volume': 32}))
                    time.sleep(1)
                    quiet = rms()
                    assert .35 < quiet / loud < .65, (quiet, loud)
                    assert process.poll() is None, (root / 'renderer.log').read_text()
                finally:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        raise
                assert process.returncode == 0, (root / 'renderer.log').read_text()
            print(f'PASS {channels} channel(s), {rate} Hz, {count} stream(s): '
                  'muted startup, looping, live volume, clean shutdown', flush=True)



if __name__ == '__main__':
    main()
