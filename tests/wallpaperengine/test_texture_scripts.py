"""Verify per-image SceneScript atlas controls through real Wayland pixels."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from PIL import Image
from test_puppet_morph import f32, render, u32


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
    with tempfile.TemporaryDirectory(prefix='lwe-texture-scripts-') as directory:
        root = Path(directory)
        (root / 'materials').mkdir()
        (root / 'shaders').mkdir()
        (root / 'shaders/atlas.vert').write_text('''uniform mat4 g_ModelViewProjectionMatrix;
uniform vec4 g_Texture0Rotation; uniform vec2 g_Texture0Translation;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=g_Texture0Translation+a_TexCoord.x*g_Texture0Rotation.xy+
a_TexCoord.y*g_Texture0Rotation.zw;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}''')
        (root / 'shaders/atlas.frag').write_text('''uniform sampler2D g_Texture0; varying vec2 v_TexCoord;
void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord);}''')
        def write(name, data):
            (root / name).write_text(json.dumps(data))
        write('project.json', {'title': 'Atlas Controls', 'type': 'scene', 'file': 'scene.json'})
        write('model.json', {'material': 'material.json', 'width': 64, 'height': 32})
        write('material.json', {'passes': [{'shader': 'atlas', 'blending': 'normal', 'textures': ['atlas']}]})
        colors = [(240, 40, 20), (20, 220, 40), (40, 20, 240)]
        atlas = Image.new('RGBA', (192, 32))
        for index, color in enumerate(colors):
            atlas.paste((*color, 255), (index * 64, 0, (index + 1) * 64, 32))
        pixels = atlas.tobytes()
        texture = b'TEXV0005\0TEXI0001\0' + u32(0, 7, 192, 32, 64, 32, 0)
        texture += b'TEXB0002\0' + u32(1, 1, 192, 32, 0, len(pixels), len(pixels)) + pixels
        texture += b'TEXS0003\0' + u32(3, 64, 32)
        for index in range(3):
            texture += u32(0) + f32(.5, index * 64, 0, 64, 0, 0, 32)
        (root / 'materials/atlas.tex').write_bytes(texture)
        cases = [('seek', 'a.setFrame(2);a.pause();', 2),
                 ('stop', 'a.setFrame(2);a.stop();', 0),
                 ('rate-zero', 'a.setFrame(1);a.rate=0;a.play();', 1)]
        for name, action, expected in cases:
            script = '''export function init(value) {
                const a=thisLayer.getTextureAnimation();
                if(a !== thisLayer.getTextureAnimation() || a.frameCount !== 3 || a.duration !== 1.5)
                    throw new Error('texture identity/metadata');
                ACTION
                console.log('ATLAS_CONTROLS_PASS');return value;
            }'''.replace('ACTION', action)
            write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                'general': {'orthogonalprojection': {'width': 256, 'height': 128}, 'clearcolor': '0 0 0'},
                'objects': [{'id': 1, 'name': 'controlled', 'image': 'model.json',
                    'origin': {'value': '96 64 0', 'script': script}},
                    {'id': 2, 'name': 'shared', 'image': 'model.json', 'origin': '176 64 0'}]})
            image = render(root, binary, args, env, delay=24)
            log = (root / 'renderer.log').read_text()
            assert 'ScriptEngine [' not in log and 'ATLAS_CONTROLS_PASS' in log, log
            actual = image.getpixel((image.width * 96 // 256, image.height // 2))
            shared = image.getpixel((image.width * 176 // 256, image.height // 2))
            assert all(abs(a-b) < 3 for a,b in zip(actual, colors[expected])), (name,actual,log)
            assert all(abs(a-b) < 3 for a,b in zip(shared, colors[1])), (name,shared,log)
            print('PASS atlas controls', name, actual, 'shared', shared, flush=True)


if __name__ == '__main__':
    main()
