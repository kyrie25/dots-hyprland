"""Verify native puppet mesh layouts and padded UVs before and after effects."""
import argparse
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import tempfile
import time

from PIL import Image


def mesh_file(version, mask):
    data = f'MDLV{version:04d}\0'.encode() + struct.pack('<3I', mask, 1, 1)
    data += b'material/MDLS_embedded\0' + struct.pack('<I', 0)
    if version >= 17:
        data += struct.pack('<6f', -32, -16, 0, 32, 16, 0)
    if version >= 15:
        data += struct.pack('<I', mask)
    vertices = bytearray()
    for x, y, u, v in [(-32, -16, 0, 0), (32, -16, 1, 0),
                        (-32, 16, 0, 1), (32, 16, 1, 1)]:
        vertices += struct.pack('<3f', x, y, 0)
        if mask & 2:
            vertices += struct.pack('<3f', 0, 0, 1)
        if mask & 4:
            vertices += struct.pack('<4f', 1, 0, 0, 1)
        vertices += struct.pack('<4I4f2f', 0, 0, 0, 0, 1, 0, 0, 0, u, v)
    data += struct.pack('<I', len(vertices)) + vertices
    data += struct.pack('<I6H', 12, 0, 1, 2, 2, 1, 3)
    if version >= 21:
        data += b'\0\0'
    if version >= 23:
        data += struct.pack('<I', 0)
    return data


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
    with tempfile.TemporaryDirectory(prefix='lwe-puppet-regression-') as directory:
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

        write('project.json', {'title': 'Puppet Regression', 'type': 'scene', 'file': 'scene.json'})
        write('model.json', {'material': 'material.json', 'puppet': 'test.mdl'})
        write('material.json', {'passes': [{'shader': 'copy', 'blending': 'normal', 'textures': ['test']}]})
        write('copy.json', {'passes': [{'shader': 'copy', 'blending': 'normal'}]})
        write('effect.json', {'passes': [{'material': 'copy.json'}]})
        for version, mask, broken_rig in [(13, 0x01800009, False), (21, 0x01800009, False),
                                           (21, 0x0180000f, False), (23, 0x0180000f, False),
                                           (21, 0x0180000f, True)]:
            mesh = mesh_file(version, mask)
            if broken_rig:
                mesh += b'MDLS0001\0' + struct.pack('<2I', 0, 1) + b'bad\0'
            (root / 'test.mdl').write_bytes(mesh)
            for padded in [False, True]:
                texture = Image.new('RGBA', (128, 64) if padded else (64, 32), (255, 0, 255, 255))
                texture.paste((255, 30, 30, 255), (0, 0, 32, 32))
                texture.paste((30, 255, 30, 255), (32, 0, 64, 32))
                pixels = texture.tobytes()
                packed = (b'TEXV0005\0TEXI0001\0' + struct.pack('<7I', 0, 3, texture.width, texture.height, 64, 32, 0)
                          + b'TEXB0002\0' + struct.pack('<7I', 1, 1, texture.width, texture.height, 0, len(pixels), len(pixels))
                          + pixels)
                (root / 'materials/test.tex').write_bytes(packed)
                for effects in [False, True]:
                    name = f'{version}-{mask:x}-{padded}-{effects}-{broken_rig}'
                    obj = {'id': 1, 'name': 'puppet', 'image': 'model.json',
                           'origin': '128 64 0', 'scale': '2 2 1'}
                    if effects:
                        obj['effects'] = [{'file': 'effect.json'}]
                    write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                                        'general': {'orthogonalprojection': {'width': 256, 'height': 128},
                                                    'clearcolor': '0 0 0'}, 'objects': [obj]})
                    capture = root / f'{name}.png'
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
                            assert 'Loaded puppet mesh' in (root / 'renderer.log').read_text(), (root / 'renderer.log').read_text()
                            with Image.open(capture) as screenshot:
                                actual = screenshot.convert('RGB')
                                left, top, right, bottom = actual.getbbox()
                                for fraction, expected in [(.25, (255, 30, 30)), (.75, (30, 255, 30))]:
                                    pixel = actual.getpixel((int(left + (right-left)*fraction), (top+bottom)//2))
                                    assert all(abs(a-b) <= 2 for a, b in zip(pixel, expected)), (name, pixel, expected)
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
                    print('PASS puppet layout/padding/effects', name, flush=True)


if __name__ == '__main__':
    main()
