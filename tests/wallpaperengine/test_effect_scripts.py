"""Verify native material/effect script owners and live effect visibility on Wayland."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from PIL import Image
from test_puppet_morph import puppet, render, u32


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
    with tempfile.TemporaryDirectory(prefix='lwe-effect-scripts-') as directory:
        root = Path(directory)
        (root / 'materials').mkdir()
        (root / 'shaders').mkdir()
        vertex = '''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}'''
        for name in ['copy', 'gain']:
            (root / f'shaders/{name}.vert').write_text(vertex)
        (root / 'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0; varying vec2 v_TexCoord;
void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord);}''')
        (root / 'shaders/gain.frag').write_text('''uniform sampler2D g_Texture0; varying vec2 v_TexCoord;
uniform float g_Gain; // {"material":"gain","default":1.0}
void main(){gl_FragColor=vec4(texSample2D(g_Texture0,v_TexCoord).rgb*g_Gain,1.0);}''')
        def write(name, value):
            (root / name).write_text(json.dumps(value))
        write('project.json', {'title': 'Effect Scripts', 'type': 'scene', 'file': 'scene.json'})
        write('model.json', {'material': 'material.json', 'width': 64, 'height': 32})
        write('material.json', {'passes': [{'shader': 'copy', 'blending': 'normal', 'textures': ['test']}]})
        write('gain.json', {'passes': [{'shader': 'gain', 'blending': 'normal'}]})
        write('effect.json', {'name': 'Gain', 'passes': [{'material': 'gain.json'}]})
        pixels = Image.new('RGBA', (64, 32), (240, 80, 40, 255)).tobytes()
        (root / 'materials/test.tex').write_bytes(b'TEXV0005\0TEXI0001\0' + u32(0, 3, 64, 32, 64, 32, 0)
            + b'TEXB0002\0' + u32(1, 1, 64, 32, 0, len(pixels), len(pixels)) + pixels)
        material_script = '''export function init(value) {
    if (thisLayer.id !== 1 || !('gain' in thisObject)) throw new Error('material owner');
    engine.setTimeout(() => {
        if (thisLayer.id !== 1 || !('gain' in thisObject)) throw new Error('material timer owner');
        console.log('MATERIAL_TIMER_PASS');
    }, 0);
    thisObject.gain = .75;
    if (Math.abs(thisObject.gain - .75) > .001) throw new Error('fractional material assignment');
    return value;
}
export function update(value) { return .5; }'''
        effect_script = '''let elapsed=0;
export function init(value) {
    if (thisObject.name !== 'Gain' || thisLayer.getEffectCount() !== 1 || thisLayer.getEffect('Gain').name !== 'Gain')
        throw new Error('effect owner');
    return false;
}
export function update(value) { return ++elapsed > 20 && elapsed < 60; }'''
        for mode, delay, expected in [('flat',5,(240,80,40)), ('flat',45,(120,40,20)),
                                      ('puppet',5,(240,80,40)), ('puppet',45,(120,40,20)),
                                      ('puppet',90,(240,80,40))]:
            write('model.json', {'material': 'material.json', 'width': 64, 'height': 32,
                                **({'puppet': 'test.mdl'} if mode == 'puppet' else {})})
            (root / 'test.mdl').write_bytes(puppet(morph_weight=0))
            write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                'general': {'orthogonalprojection': {'width': 256, 'height': 128}, 'clearcolor': '0 0 0'},
                'objects': [{'id': 1, 'name': 'image', 'image': 'model.json', 'origin': '128 64 0',
                    'effects': [{'file': 'effect.json', 'name': 'Gain', 'visible': {'value': True, 'script': effect_script},
                        'passes': [{'constantshadervalues': {'gain': {'value': 1, 'script': material_script}}}]}]}]})
            image = render(root, binary, args, env, delay=delay)
            log = (root / 'renderer.log').read_text()
            assert 'ScriptEngine [' not in log and 'SceneScript timer:' not in log and 'MATERIAL_TIMER_PASS' in log, log
            pixel = image.getpixel((image.width // 2, image.height // 2))
            assert all(abs(a-b) < 3 for a,b in zip(pixel,expected)), (delay,pixel,expected,log)
            print('PASS native effect/material scripts', mode, delay, pixel, flush=True)


if __name__ == '__main__':
    main()
