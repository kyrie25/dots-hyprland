"""Verify custom GIF/video timing and authored image dimensions with Wayland captures."""
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
    parser.add_argument('--monitor', required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    env = dict(os.environ, LD_LIBRARY_PATH=str(binary.parent), __GL_THREADED_OPTIMIZATIONS='0')
    env.pop('__GLX_VENDOR_LIBRARY_NAME', None)
    env.pop('EGL_PLATFORM', None)
    with tempfile.TemporaryDirectory(prefix='lwe-custom-image-regression-') as directory:
        root = Path(directory)
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        frames = [Image.new('RGB', (64, 32), color) for color in colors]
        frames[0].save(root / 'timing.gif', save_all=True, append_images=frames[1:],
                       duration=[1000, 1000, 1000], loop=0, optimize=False)
        for i, frame in enumerate(frames):
            frame.save(root / f'frame{i}.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-framerate', '1', '-i', str(root / 'frame%d.png'),
                        '-r', '30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(root / 'timing.mp4')], check=True)
        (root / 'shaders').mkdir()
        (root / 'shaders/copy.vert').write_text('''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}''')
        (root / 'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0; varying vec2 v_TexCoord;
void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord);}''')

        def write(name, value):
            (root / name).write_text(json.dumps(value))

        write('project.json', {'title': 'Custom Image Regression', 'type': 'scene', 'file': 'scene.json'})
        write('model.json', {'material': 'material.json', 'width': 320, 'height': 240})
        write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                            'general': {'orthogonalprojection': {'width': 640, 'height': 480},
                                        'clearcolor': '0 0 0'},
                            'objects': [{'id': 1, 'name': 'custom', 'origin': '320 240 0',
                                         'image': 'model.json', 'size': '320 240'}]})
        first_bounds = None
        for extension in ['gif', 'mp4']:
            write('material.json', {'passes': [{'shader': 'copy', 'blending': 'normal',
                                                'textures': [str(root / f'timing.{extension}')]}]})
            for frame_count, expected in [(8, colors[0]), (40, colors[1]), (70, colors[2]), (100, colors[0])]:
                capture = root / f'{extension}-{frame_count}.png'
                with (root / 'renderer.log').open('w') as log:
                    process = subprocess.Popen([str(binary), '--fps', '30', '--silent', '--noautomute',
                        '--no-fullscreen-pause', '--anti-aliasing', '2', '--layer', 'background',
                        '--screen-root', args.monitor, '--assets-dir', str(args.assets),
                        '--screenshot', str(capture), '--screenshot-delay', str(frame_count), str(root)],
                        env=env, stdout=log, stderr=log, start_new_session=True)
                    try:
                        deadline = time.monotonic() + 25
                        while not capture.exists() and time.monotonic() < deadline:
                            assert process.poll() is None, (root / 'renderer.log').read_text()
                            time.sleep(.1)
                        assert capture.exists(), (root / 'renderer.log').read_text()
                        time.sleep(.2)
                        with Image.open(capture) as image:
                            rgb = image.convert('RGB')
                            actual = rgb.getpixel((rgb.width // 2, rgb.height // 2))
                            assert all(abs(a - e) <= 3 for a, e in zip(actual, expected)), (extension, frame_count, actual, expected)
                            bounds = rgb.getbbox()
                            if first_bounds is None:
                                first_bounds = bounds
                            assert bounds == first_bounds, (extension, bounds, first_bounds)
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
                print('PASS custom', extension, frame_count, 'timing and authored bounds', flush=True)


if __name__ == '__main__':
    main()
