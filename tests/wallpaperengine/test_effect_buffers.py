"""Capture real Wayland draws to verify effect alpha and opaque scene alpha."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from PIL import Image


VERTEX = '''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position;
attribute vec2 a_TexCoord;
varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}
'''


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
    with tempfile.TemporaryDirectory(prefix='lwe-effect-regression-') as directory:
        root = Path(directory)
        (root / 'shaders').mkdir()
        for name in ['alpha', 'probe', 'copy']:
            (root / f'shaders/{name}.vert').write_text(VERTEX)
        (root / 'shaders/alpha.frag').write_text('void main(){gl_FragColor=vec4(1.0,0.0,0.0,0.25);}')
        (root / 'shaders/probe.frag').write_text('''uniform sampler2D g_Texture0;
varying vec2 v_TexCoord;
void main(){gl_FragColor=vec4(vec3(texSample2D(g_Texture0,v_TexCoord).a),1.0);}''')
        (root / 'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0;
varying vec2 v_TexCoord;
void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord);}''')

        def write(name, value):
            (root / name).write_text(json.dumps(value))

        write('project.json', {'title': 'Alpha Regression', 'type': 'scene', 'file': 'scene.json'})
        write('alpha.json', {'passes': [{'shader': 'alpha', 'blending': 'normal'}]})
        write('probe.json', {'passes': [{'shader': 'probe', 'blending': 'normal'}]})
        write('copy.json', {'passes': [{'shader': 'copy', 'blending': 'normal',
                                     'textures': ['_rt_FullFrameBuffer']}]})
        write('effect.json', {'passes': [{'material': 'probe.json'}]})
        for name in ['alpha', 'copy']:
            write(f'{name}-model.json', {'material': f'{name}.json', 'width': 640,
                                         'height': 480, 'solidlayer': True})

        def image(identifier, material, effects=False):
            value = {'id': identifier, 'name': material, 'image': f'{material}-model.json',
                     'origin': '320 240 0', 'size': '640 480'}
            if effects:
                value['effects'] = [{'file': 'effect.json'}]
            return value

        cases = [
            ('intermediate-alpha', [image(1, 'alpha', True)], 64),
            ('scene-image-alpha', [image(1, 'alpha'), image(2, 'copy', True)], 255),
            ('scene-text-alpha', [{'id': 1, 'name': 'text', 'origin': '320 240 0',
                                   'text': 'ALPHA', 'pointsize': 70, 'alpha': .5},
                                  image(2, 'copy', True)], 255),
        ]
        for name, objects, expected in cases:
            write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                                'general': {'orthogonalprojection': {'width': 640, 'height': 480},
                                            'clearcolor': '0 0 0'}, 'objects': objects})
            capture = root / f'{name}.png'
            with (root / 'renderer.log').open('w') as log:
                process = subprocess.Popen([str(binary), '--fps', '30', '--silent', '--noautomute',
                    '--no-fullscreen-pause', '--anti-aliasing', '2', '--layer', 'background',
                    '--screen-root', args.monitor, '--assets-dir', str(args.assets),
                    '--screenshot', str(capture), '--screenshot-delay', '20', str(root)],
                    env=env, stdout=log, stderr=log, start_new_session=True)
                try:
                    deadline = time.monotonic() + 20
                    while not capture.exists() and time.monotonic() < deadline:
                        assert process.poll() is None, (root / 'renderer.log').read_text()
                        time.sleep(.1)
                    assert capture.exists(), (root / 'renderer.log').read_text()
                    time.sleep(.2)
                    with Image.open(capture) as screenshot:
                        w, h = screenshot.size
                        # Ignore fit-mode margins; inspect the central area including glyph edges.
                        bounds = screenshot.convert('RGB').crop((w // 3, h // 3, 2*w // 3, 2*h // 3)).getextrema()
                        assert all(abs(low - expected) <= 1 and abs(high - expected) <= 1
                                   for low, high in bounds), (name, expected, bounds)
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
            print('PASS', name, flush=True)


if __name__ == '__main__':
    main()
