"""Render synthetic native MDMP/MDLA morph and bone-alpha tracks on Wayland."""
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

from PIL import Image


def u32(*values):
    return struct.pack('<' + 'I' * len(values), *values)


def f32(*values):
    return struct.pack('<' + 'f' * len(values), *values)


def puppet(morph_weight=1, bone_alpha=1, morph_alpha=None, modifier=False, broken=False):
    flags = (4 if bone_alpha != 1 else 0) | (0x1000 if morph_alpha is not None else 0) | (0x2000 if modifier else 0)
    mask = 0x01810008
    mesh = b'MDLV0021\0' + u32(mask, 1, 1) + b'material\0' + u32(flags)
    mesh += f32(-32, -16, 0, 32, 16, 0) + u32(mask)
    vertices = bytearray()
    for index, (x, y, u, v) in enumerate([(-32, -16, 0, 0), (32, -16, 1, 0),
                                         (-32, 16, 0, 1), (32, 16, 1, 1)]):
        vertices += f32(x, y, 0, index + 1) + u32(0, 0, 0, 0) + f32(1, 0, 0, 0, u, v)
    mesh += u32(len(vertices)) + vertices + u32(12) + struct.pack('<6H', 0, 1, 2, 2, 1, 3) + b'\0\0'
    # A v1 rig has no extras/constraints; later MDLA tracks are still allowed.
    identity = f32(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    skeleton = u32(1) + b'root\0' + u32(0, 0xffffffff, 64) + identity + b'\0'
    morph = struct.pack('<H', 1) + f32(32) + u32(4) + struct.pack('<Q', 99) + b'move\0'
    morph += u32(24) + struct.pack('<12h', *([32767, 0, 0] * 4))
    if morph_alpha is not None:
        morph += u32(8) + struct.pack('<4h', *([round(morph_alpha * 32767)] * 4))
    if modifier:
        if modifier == 'radial':
            morph += u32(0, 0) + f32(32, 64)
        else:
            # The left two vertices are outside the axis range, the right two inside.
            morph += u32(0, 2) + f32(-16, 16)
    clip = u32(1) + struct.pack('<Q', 42) + b'test\0loop\0' + f32(1) + u32(1, 0, 1)
    clip += u32(0, 72) + f32(*([0, 0, 0, 0, 0, 0, 1, 1, 1] * 2))
    clip += u32(0) + b'\1' + u32(0, 8) + f32(bone_alpha, bone_alpha)
    clip += b'\1' + u32(1, 0) + struct.pack('<HH', 1, 0) + u32(8) + f32(morph_weight, morph_weight)
    clip += u32(0)  # Clip events.
    sections = [(b'MDLS0001\0', skeleton), (b'MDMP0001\0', morph), (b'MDLA0004\0', clip)]
    for tag, payload in sections:
        mesh += tag + u32(len(mesh) + len(tag) + 4 + len(payload)) + payload
    if broken:
        # Corrupt only the morph payload; the rig and its bone animation survive.
        start = mesh.index(b'MDMP0001\0')
        mesh = bytearray(mesh)
        mesh[start + 19:start + 23] = u32(0xffffffff)
    return mesh


def ordered_puppet(rest=(0, 0), orders=(0, 0), animated=None):
    mask = 0x01810008
    mesh = b'MDLV0021\0' + u32(mask, 1, 1) + b'material\0' + u32(8)
    mesh += f32(-32, -16, 0, 32, 16, 0) + u32(mask)
    vertices = bytearray()
    for part in range(2):
        for x, y, u, v in [(-32, -16, 0, 0), (32, -16, 1, 0),
                            (-32, 16, 0, 1), (32, 16, 1, 1)]:
            vertices += f32(x, y, 0, 0) + u32(part, 0, 0, 0) + f32(1, 0, 0, 0, (u + part) / 2, v)
    mesh += u32(len(vertices)) + vertices + u32(24)
    mesh += struct.pack('<12H', 0, 1, 2, 2, 1, 3, 4, 5, 6, 6, 5, 7)
    mesh += b'\0\1' + u32(32)
    for part in range(2):
        mesh += u32(part, orders[part] & 0xffffffff, part * 6, 6)
    identity = f32(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    skeleton = u32(2)
    for part in range(2):
        skeleton += f'part{part}\0'.encode() + u32(0, 0xffffffff, 64) + identity + b'\0'
    skeleton += struct.pack('<H', 0) + b'\0' + u32(0) + struct.pack('<HH', 0, 0)
    skeleton += b'\0\0\1' + struct.pack('<2i', *rest)
    clip = u32(1) + struct.pack('<Q', 42) + b'order\0loop\0' + f32(1) + u32(1, 0, 2)
    for _ in range(2):
        clip += u32(0, 72) + f32(*([0, 0, 0, 0, 0, 0, 1, 1, 1] * 2))
    clip += u32(0) + b'\0\0' + f32(*([0] * 6)) + bytes([animated is not None])
    if animated is not None:
        for order in animated:
            clip += u32(0, 8) + f32(order, order)
    clip += u32(0)
    for tag, payload in [(b'MDLS0003\0', skeleton), (b'MDLA0006\0', clip)]:
        mesh += tag + u32(len(mesh) + len(tag) + 4 + len(payload)) + payload
    return mesh


def render(root, binary, args, env, delay=12):
    capture = root / 'capture.png'
    capture.unlink(missing_ok=True)
    with (root / 'renderer.log').open('w') as log:
        process = subprocess.Popen([str(binary), '--fps', '30', '--silent', '--noautomute',
            '--no-fullscreen-pause', '--anti-aliasing', '2', '--layer', 'background',
            '--screen-root', args.monitor, '--assets-dir', str(args.assets),
            '--screenshot', str(capture), '--screenshot-delay', str(delay), str(root)],
            env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            deadline = time.monotonic() + 25
            while not capture.exists() and time.monotonic() < deadline:
                assert process.poll() is None, (root / 'renderer.log').read_text()
                time.sleep(.1)
            assert capture.exists(), (root / 'renderer.log').read_text()
            time.sleep(.1)
            with Image.open(capture) as image:
                result = image.convert('RGB')
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
    return result


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
    with tempfile.TemporaryDirectory(prefix='lwe-puppet-morph-') as directory:
        root = Path(directory)
        (root / 'materials').mkdir()
        (root / 'shaders').mkdir()
        (root / 'shaders/copy.vert').write_text('''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}''')
        (root / 'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0; varying vec2 v_TexCoord;
void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord);}''')
        (root / 'shaders/tinted.vert').write_text((root / 'shaders/copy.vert').read_text())
        (root / 'shaders/tinted.frag').write_text('''uniform sampler2D g_Texture0; uniform vec4 g_Color4;
varying vec2 v_TexCoord; void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord)*g_Color4;}''')
        def write(name, value):
            (root / name).write_text(json.dumps(value))
        write('project.json', {'title': 'Morph Regression', 'type': 'scene', 'file': 'scene.json'})
        write('model.json', {'material': 'material.json', 'puppet': 'test.mdl', 'width': 64, 'height': 32})
        write('material.json', {'passes': [{'shader': 'tinted', 'blending': 'normal', 'textures': ['test']}]})
        write('copy.json', {'passes': [{'shader': 'copy', 'blending': 'normal'}]})
        write('effect.json', {'name': 'Identity', 'passes': [{'material': 'copy.json'}]})
        pixels = Image.new('RGBA', (64, 32), (240, 80, 40, 255)).tobytes()
        (root / 'materials/test.tex').write_bytes(b'TEXV0005\0TEXI0001\0' + u32(0, 3, 64, 32, 64, 32, 0)
            + b'TEXB0002\0' + u32(1, 1, 64, 32, 0, len(pixels), len(pixels)) + pixels)
        baseline = {}
        cases = [('bind', dict(morph_weight=0), 1), ('position', {}, 1),
                 ('bone-alpha', dict(bone_alpha=.5), .5), ('morph-alpha', dict(morph_alpha=.5), .5),
                 ('combined-alpha', dict(bone_alpha=.5, morph_alpha=.5), .25),
                 ('bone-modifier', dict(modifier=True), 1),
                 ('bone-modifier-alpha', dict(modifier=True, morph_alpha=.5), .5),
                 ('radial-modifier', dict(modifier='radial'), 1),
                 ('radial-modifier-alpha', dict(modifier='radial', morph_alpha=.5), .5),
                 ('color-tint', dict(bone_alpha=.5), .5),
                 ('malformed', dict(broken=True), 1)]
        for effects in (False, True):
            for name, options, alpha in cases:
                (root / 'test.mdl').write_bytes(puppet(**options))
                obj = {'id': 1, 'name': 'puppet', 'image': 'model.json', 'origin': '128 64 0',
                       'animationlayers': [{'animation': 42, 'visible': True, 'blend': 1}]}
                if name == 'color-tint':
                    obj['color'] = '0.5 1 1'
                if effects:
                    obj['effects'] = [{'file': 'effect.json'}]
                write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                    'general': {'orthogonalprojection': {'width': 256, 'height': 128}, 'clearcolor': '0 0 0'},
                    'objects': [obj]})
                rgb = render(root, binary, args, env)
                bounds = rgb.getbbox()
                assert bounds is not None, (name, 'invisible puppet', (root / 'renderer.log').read_text())
                color = rgb.getpixel(((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2))
                expected = (120, 80, 40) if name == 'color-tint' else (240, 80, 40)
                assert all(abs(a - b * alpha) < 3 for a, b in zip(color, expected)), (name, effects, color, alpha)
                if name == 'bind':
                    baseline[effects] = bounds
                elif name == 'malformed':
                    assert bounds == baseline[effects], (name, bounds, baseline[effects])
                elif name.startswith('bone-modifier'):
                    assert bounds[0] == baseline[effects][0] and bounds[2] > baseline[effects][2], (name, bounds)
                elif name.startswith('radial-modifier'):
                    t = (math.hypot(32, 16) - 32) / 32
                    # The scene is rasterized at 256 pixels before output scaling.
                    displacement = round(32 * t * t * (3 - 2 * t)) * rgb.width / 256
                    assert abs(bounds[0] - baseline[effects][0] - displacement) < 2, (name, bounds, displacement)
                    assert abs(bounds[2] - baseline[effects][2] - displacement) < 2, (name, bounds, displacement)
                else:
                    before = baseline[effects]
                    assert bounds[0] > before[0] + 100 and bounds[2] > before[2] + 100, (name, effects, bounds, before)
                    assert abs((bounds[2] - bounds[0]) - (before[2] - before[0])) <= 2, (name, bounds, before)
                print('PASS puppet', name, 'effects', effects, flush=True)
        pixels = Image.new('RGBA', (64, 32), (240, 80, 40, 255))
        pixels.paste((40, 160, 240, 255), (32, 0, 64, 32))
        data = pixels.tobytes()
        (root / 'materials/test.tex').write_bytes(b'TEXV0005\0TEXI0001\0' + u32(0, 3, 64, 32, 64, 32, 0)
            + b'TEXB0002\0' + u32(1, 1, 64, 32, 0, len(data), len(data)) + data)
        for effects in (False, True):
            for name, options, visible, expected in [
                ('file-order', {}, False, (40, 160, 240)),
                ('signed-order', {'orders': (0, -1)}, False, (240, 80, 40)),
                ('animated-order', {'animated': (2, 0)}, True, (240, 80, 40)),
                ('hidden-track', {'animated': (2, 0)}, False, (40, 160, 240)),
                ('rest-order', {'rest': (2, 0), 'orders': (0, 3)}, False, (240, 80, 40)),
                ('integer-tie', {'animated': (.9, .8)}, True, (40, 160, 240)),
            ]:
                (root / 'test.mdl').write_bytes(ordered_puppet(**options))
                obj = {'id': 1, 'name': 'puppet', 'image': 'model.json', 'origin': '128 64 0',
                       'animationlayers': [{'animation': 42, 'visible': visible, 'blend': 1}]}
                if effects:
                    obj['effects'] = [{'file': 'effect.json'}]
                write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                    'general': {'orthogonalprojection': {'width': 256, 'height': 128}, 'clearcolor': '0 0 0'},
                    'objects': [obj]})
                image = render(root, binary, args, env)
                color = image.getpixel((image.width // 2, image.height // 2))
                assert all(abs(a - b) < 3 for a, b in zip(color, expected)), (name, effects, color, expected)
                print('PASS draw order', name, 'effects', effects, flush=True)


if __name__ == '__main__':
    main()
