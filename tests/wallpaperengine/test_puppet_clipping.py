"""Render native MDLV23 clipping masks through the existing effects pipeline."""
import argparse
import json
import os
from pathlib import Path
import struct
import tempfile

from PIL import Image
from test_puppet_morph import f32, render, u32


def puppet(records, source_half=True, bone_alpha=None, reverse=False):
    mask = 0x01810008
    flags = 8 | (4 if bone_alpha is not None else 0)
    mesh = b'MDLV0023\0' + u32(mask, 1, 1) + b'material\0' + u32(flags)
    mesh += f32(-32, -16, 0, 32, 16, 0) + u32(mask)
    vertices = bytearray()
    for part in range(3):
        right = 0 if part == 0 and source_half else 32
        for x, y, u, v in [(-32, -16, 0, 0), (right, -16, 1, 0),
                            (-32, 16, 0, 1), (right, 16, 1, 1)]:
            vertices += f32(x, y, 0, 0) + u32(part, 0, 0, 0) + f32(1, 0, 0, 0, (u + part) / 3, v)
    indices = [i + part * 4 for part in range(3) for i in [0, 1, 2, 2, 1, 3]]
    mesh += u32(len(vertices)) + vertices + u32(len(indices) * 2) + struct.pack('<18H', *indices)
    mesh += b'\0\1' + u32(48)
    for part in range(3):
        mesh += u32(part, 0, part * 6, 6)
    mesh += u32(len(records))
    for index, (name, flags, targets, sources) in enumerate(records):
        mesh += struct.pack('<Q', index) + name.encode() + b'\0' + u32(flags)
        for parts in (targets, sources):
            mesh += u32(len(parts)) + u32(*parts)
    identity = f32(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    skeleton = u32(3)
    for part in range(3):
        skeleton += f'part{part}\0'.encode() + u32(0, 0xffffffff, 64) + identity + b'\0'
    skeleton += struct.pack('<H', 0) + b'\0' + u32(0) + struct.pack('<HH', 0, 0) + b'\0\0\0'
    clip = u32(1) + struct.pack('<Q', 42) + b'clip\0loop\0' + f32(1) + u32(1, 0, 3)
    for _ in range(3):
        clip += u32(0, 72) + f32(*([0, 0, 0, 0, 0, 0, 1, 1, 1] * 2))
    clip += u32(0) + bytes([bone_alpha is not None])
    if bone_alpha is not None:
        for alpha in bone_alpha:
            clip += u32(0, 8) + f32(alpha, alpha)
    clip += b'\0' + f32(*([0] * 6)) + bytes([reverse])
    if reverse:
        for order in (2, 1, 0):
            clip += u32(0, 8) + f32(order, order)
    clip += u32(0)
    for tag, payload in [(b'MDLS0003\0', skeleton), (b'MDLA0006\0', clip)]:
        mesh += tag + u32(len(mesh) + len(tag) + 4 + len(payload)) + payload
    return mesh


def texture(path, pixels, padded=False):
    width, height = pixels.size
    if padded:
        canvas = Image.new('RGBA', (256, 64))
        canvas.paste(pixels)
    else:
        canvas = pixels
    data = canvas.tobytes()
    path.write_bytes(b'TEXV0005\0TEXI0001\0' + u32(0, 3, canvas.width, canvas.height, width, height, 0)
        + b'TEXB0002\0' + u32(1, 1, canvas.width, canvas.height, 0, len(data), len(data)) + data)


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
    with tempfile.TemporaryDirectory(prefix='lwe-clipping-') as directory:
        root = Path(directory)
        (root / 'materials').mkdir()
        (root / 'shaders').mkdir()
        (root / 'shaders/copy.vert').write_text('''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}''')
        (root / 'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0; varying vec2 v_TexCoord;
void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord);}''')
        def write(name, value):
            (root / name).write_text(json.dumps(value))
        write('project.json', {'title': 'Clipping Regression', 'type': 'scene', 'file': 'scene.json'})
        write('model.json', {'material': 'material.json', 'puppet': 'test.mdl', 'width': 64, 'height': 32})
        write('material.json', {'passes': [{'shader': 'copy', 'blending': 'normal', 'textures': ['test']}]})
        write('copy.json', {'passes': [{'shader': 'copy', 'blending': 'normal'}]})
        write('effect.json', {'name': 'Identity', 'passes': [{'material': 'copy.json'}]})
        pixels = Image.new('RGBA', (96, 32), (240, 80, 40, 255))
        pixels.paste((40, 160, 240, 255), (32, 0, 64, 32))
        pixels.paste((80, 240, 40, 255), (64, 0, 96, 32))
        mask = Image.new('RGBA', pixels.size, (255, 255, 255, 255))
        blue, green, black = (40, 160, 240), (80, 240, 40), (0, 0, 0)
        cases = [
            ('normal', [('mask', 4, [1, 2], [0])], {}, green, black),
            ('inverted', [('mask', 6, [1, 2], [0])], {}, black, green),
            ('at-targets', [('mask', 12, [1, 2], [0])], {}, green, black),
            ('additive', [('mask', 5, [1, 2], [0])], {}, (120, 255, 255), black),
            ('soft-mask', [('soft', 4, [1, 2], [0])], {}, (50, 160, 80), black),
            ('nested', [('mask', 4, [1], [0]), ('mask', 4, [2], [1])], {}, green, black),
            ('nested-inverted', [('mask', 6, [1], [0]), ('mask', 4, [2], [1])], {}, black, green),
            ('nested-reordered', [('mask', 4, [1], [0]), ('mask', 4, [2], [1])], {'reverse': True}, blue, black),
            ('bone-alpha', [('mask', 4, [1, 2], [0])], {'bone_alpha': (.5, 1, 1)}, (28, 90, 55), black),
            ('target-alpha', [('mask', 4, [1, 2], [0])], {'bone_alpha': (1, 1, .5)}, (60, 200, 140), black),
            ('malformed', [('mask', 4, [1, 2], [99])], {}, green, green),
        ]
        for padded in (False, True):
            texture(root / 'materials/test.tex', pixels, padded)
            texture(root / 'materials/mask.tex', mask, padded)
            texture(root / 'materials/soft.tex', Image.new('RGBA', pixels.size, (128, 128, 128, 255)), padded)
            for effects in (False, True):
                for name, records, options, left, right in cases:
                    (root / 'test.mdl').write_bytes(puppet(records, **options))
                    obj = {'id': 1, 'name': 'puppet', 'image': 'model.json', 'origin': '128 64 0',
                           'animationlayers': [{'animation': 42, 'visible': True, 'blend': 1}]}
                    if effects:
                        obj['effects'] = [{'file': 'effect.json'}]
                    write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                        'general': {'orthogonalprojection': {'width': 256, 'height': 128}, 'clearcolor': '0 0 0'},
                        'objects': [obj]})
                    image = render(root, binary, args, env)
                    for fraction, expected in [(112 / 256, left), (144 / 256, right)]:
                        color = image.getpixel((int(image.width * fraction), image.height // 2))
                        assert all(abs(a - b) < 4 for a, b in zip(color, expected)), (name, padded, effects, color, expected)
                    print('PASS clipping', name, 'padding', padded, 'effects', effects, flush=True)


if __name__ == '__main__':
    main()
