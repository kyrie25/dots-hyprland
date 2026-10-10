"""Verify EXIF orientation for external images and authored packed-texture UVs."""
import argparse
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import tempfile
import time

from PIL import Image, ImageOps


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
    with tempfile.TemporaryDirectory(prefix='lwe-orientation-regression-') as directory:
        root = Path(directory)
        (root / 'shaders').mkdir()
        (root / 'materials').mkdir()
        (root / 'shaders/copy.vert').write_text('''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}''')
        (root / 'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0; varying vec2 v_TexCoord;
void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord);}''')

        def write(name, value):
            (root / name).write_text(json.dumps(value))

        write('project.json', {'title': 'Orientation Regression', 'type': 'scene', 'file': 'scene.json'})
        write('model.json', {'material': 'material.json', 'width': 320, 'height': 240})
        write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                            'general': {'orthogonalprojection': {'width': 640, 'height': 480},
                                        'clearcolor': '0 0 0'},
                            'objects': [{'id': 1, 'name': 'custom', 'origin': '320 240 0',
                                         'image': 'model.json', 'size': '320 240'}]})
        source = Image.new('RGB', (128, 64))
        colors = [(240, 30, 30), (30, 240, 30), (30, 30, 240), (240, 240, 30)]
        for box, color in zip([(0, 0, 64, 32), (64, 0, 128, 32),
                               (0, 32, 64, 64), (64, 32, 128, 64)], colors):
            source.paste(color, box)
        for orientation in [1, 6, 8]:
            exif = Image.Exif()
            exif[274] = orientation
            jpeg = root / 'orientation.jpg'
            source.save(jpeg, quality=100, subsampling=0, exif=exif)
            data = jpeg.read_bytes()
            packed = (b'TEXV0005\0TEXI0001\0' + struct.pack('<7I', 0, 2, 128, 64, 128, 64, 0)
                      + b'TEXB0003\0' + struct.pack('<8I', 1, 2, 1, 128, 64, 0, len(data), len(data))
                      + data)
            (root / 'materials/packed.tex').write_bytes(packed)
            for kind, texture in [('external', str(jpeg)), ('packed', 'packed')]:
                write('material.json', {'passes': [{'shader': 'copy', 'blending': 'normal',
                                                   'textures': [texture]}]})
                capture = root / f'{kind}-{orientation}.png'
                with (root / 'renderer.log').open('w') as log:
                    process = subprocess.Popen([str(binary), '--fps', '30', '--silent', '--noautomute',
                        '--no-fullscreen-pause', '--anti-aliasing', '2', '--layer', 'background',
                        '--screen-root', args.monitor, '--assets-dir', str(args.assets),
                        '--screenshot', str(capture), '--screenshot-delay', '8', str(root)],
                        env=env, stdout=log, stderr=log, start_new_session=True)
                    try:
                        deadline = time.monotonic() + 20
                        while not capture.exists() and time.monotonic() < deadline:
                            assert process.poll() is None, (root / 'renderer.log').read_text()
                            time.sleep(.1)
                        assert capture.exists(), (root / 'renderer.log').read_text()
                        time.sleep(.2)
                        with Image.open(jpeg) as encoded, Image.open(capture) as screenshot:
                            expected = ImageOps.exif_transpose(encoded) if kind == 'external' else encoded
                            actual = screenshot.convert('RGB')
                            bounds = actual.getbbox()
                            assert bounds is not None
                            left, top, right, bottom = bounds
                            for x, y in [(.25, .25), (.75, .25), (.25, .75), (.75, .75)]:
                                pixel = actual.getpixel((int(left + (right-left)*x), int(top + (bottom-top)*y)))
                                reference = expected.getpixel((int(expected.width*x), int(expected.height*y)))
                                assert all(abs(a-b) <= 3 for a, b in zip(pixel, reference)), (kind, orientation, pixel, reference)
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
                print('PASS', kind, 'JPEG orientation', orientation, flush=True)


if __name__ == '__main__':
    main()
