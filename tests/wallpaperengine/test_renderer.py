"""Run native SceneScript and live controls on disposable Wayland renderers.

Requires two connected outputs, renderer assets, and Pillow. No user config is
changed. Temporary wallpaper layers disappear when the test processes exit.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import struct

from PIL import Image


SCRIPT = r'''
let tested = false;
let ticks = 0;
let elapsed = 0;
let timerCalls = 0;
let timerOrder = [];
let timerPass = false;
const textAudio = engine.registerAudioBuffers(engine.AUDIO_RESOLUTION_32);
export function init(value) {
    if (!thisScene.getLayer('late-image') || textAudio.average.length !== 32)
        throw new Error('deferred text module/native audio');
    thisLayer.text = value;
    console.log('TEXT_INIT_PASS');
}
function check(value, expected, message) {
    for (let i = 0; i < expected.length; i++) {
        if (Math.abs(value['xyzw'[i]] - expected[i]) > .0001)
            throw new Error(message + ': component ' + i);
    }
}
export function update(text) {
    if (!tested) {
        tested = true;
        try {
            const layer = globalThis.thisScene.getLayer('test');
            const vectors = [layer.spacing, layer.origin, layer.color];
            for (let i = 0; i < vectors.length; i++) {
                const v = vectors[i];
                const n = i + 2;
                const Ctor = v.constructor;
                const a = new Ctor({x:12, y:6, ...(n > 2 ? {z:9} : {}), ...(n > 3 ? {w:15} : {})});
                const b = new Ctor({x:3, y:2, ...(n > 2 ? {z:4} : {}), ...(n > 3 ? {w:5} : {})});
                const result = a.subtract(b);
                check(result, [9,4,5,10].slice(0,n), 'receiver minus argument');
                check(a.subtract(2), [10,4,7,13].slice(0,n), 'scalar subtraction');
                result.x = 100;
                check(a, [12,6,9,15].slice(0,n), 'detached result');
                if (a.missing !== undefined) throw new Error('unknown property');
                const numeric = n === 2 ? new Ctor(12,6) : n === 3 ? new Ctor(12,6,9) : new Ctor(12,6,9,15);
                check(numeric, [12,6,9,15].slice(0,n), 'numeric constructor');
                check(new Ctor(), Array(n).fill(0), 'zero constructor');
                let caught = 0;
                for (const f of [() => a.subtract(), () => a.subtract('bad'), () => new Ctor(undefined)]) {
                    try { f(); } catch(e) { if (!(e instanceof TypeError)) throw e; caught++; }
                }
                if (caught !== 3) throw new Error('invalid arguments');
                // Keep a temporary vector alive until the JS context is released.
                globalThis['retainedVector' + n] = a;
            }
            const v3 = new vectors[1].constructor({x:12,y:6,z:9});
            check(v3.subtract(new vectors[0].constructor({x:3,y:2})), [9,4,9], 'Vec3 minus Vec2');
            console.log('VECTOR_PASS');
            const timerEngine = globalThis.engine;
            if (timerEngine.setTimeout(12) !== null || timerEngine.setInterval(() => {}, 0) !== null)
                throw new Error('invalid timer arguments');
            const cancel = timerEngine.setTimeout(() => { throw new Error('cancelled timer ran'); }, 0);
            if (!cancel() || cancel()) throw new Error('timer cancellation');
            timerEngine.setTimeout(() => {
                timerOrder.push('first');
                timerEngine.setTimeout(() => timerOrder.push('nested'), 0);
            }, 0);
            timerEngine.setTimeout(() => timerOrder.push('second'), 0);
            let cancelOther;
            timerEngine.setTimeout(() => {
                if (!cancelOther()) throw new Error('cancellation of another due timer');
            }, 0);
            cancelOther = timerEngine.setTimeout(() => { throw new Error('cancelled due timer ran'); }, 0);
            const stopInterval = timerEngine.setInterval(() => {
                timerCalls++;
                if (timerCalls === 3 && !stopInterval()) throw new Error('self cancellation');
            }, 25.5);
            timerEngine.setTimeout(() => {
                if (timerCalls !== 3 || timerOrder.join(',') !== 'first,second,nested')
                    throw new Error('timer lifetime/order: ' + timerCalls + '/' + timerOrder);
                timerPass = true;
                console.log('TIMER_PASS');
            }, 500);
        } catch(e) { console.log('VECTOR_FAIL ' + String(e)); }
    }
    ticks++;
    elapsed += thisScene.dt;
    if (elapsed >= 1) {
        console.log('FRAME_RATE ' + ticks / elapsed);
        elapsed = 0;
        ticks = 0;
    }
    return text;
}
'''


def sound_timer_script(identifier):
    return '''
export const marker = %d;
const spectra = [16, 32, 64].map(resolution => engine.registerAudioBuffers(resolution));
const detached = engine.registerAudioBuffers(16);
detached.left.buffer.transfer();
detached.right.buffer.transfer();
let invalidResolution = false;
try { engine.registerAudioBuffers(17); } catch(e) { invalidResolution = e instanceof RangeError; }
let scheduled = false;
let scopeError = false;
try { engine.setTimeout(() => {}, 10); } catch(e) { scopeError = e instanceof SyntaxError; }
export function update(value) {
    if (detached.left.length !== 0 || detached.right.length !== 0 ||
        !Number.isFinite(detached.average[0]))
        throw new Error('detached audio buffer handling');
    for (let index = 0; index < spectra.length; index++) {
        const resolution = [16, 32, 64][index];
        const spectrum = spectra[index];
        for (const channel of ['left', 'right', 'average'])
            if (!(spectrum[channel] instanceof Float32Array) || spectrum[channel].length !== resolution)
                throw new Error('audio buffer layout');
        for (let bin = 0; bin < resolution; bin++) {
            const first = bin * 64 / resolution;
            const last = (bin + 1) * 64 / resolution;
            const combined = Math.max(...spectra[2].average.slice(first, last));
            if (!Number.isFinite(spectrum.average[bin]) || Math.abs(spectrum.average[bin] - combined) > .0001)
                throw new Error('audio buffer channels');
        }
    }
    if (!scheduled) {
        scheduled = true;
        if (!scopeError) throw new Error('timer global scope');
        if (!invalidResolution) throw new Error('audio buffer resolution validation');
        let runtimeRegistration = false;
        try { engine.registerAudioBuffers(); } catch(e) { runtimeRegistration = e instanceof TypeError; }
        if (!runtimeRegistration) throw new Error('audio buffer global scope');
        engine.setTimeout(function() {
            if (this.marker !== marker || thisLayer.origin.x !== marker)
                throw new Error('timer script owner');
            engine.setTimeout(function() {
                if (this.marker !== marker || thisLayer.origin.x !== marker)
                    throw new Error('nested timer script owner');
                console.log('MODULE_TIMER_PASS ' + marker);
                console.log('DETACHED_AUDIO_PASS ' + marker);
            }, 0);
        }, 50);
    }
    return value;
}
''' % identifier


IMAGE_SCRIPT = r'''
import { token } from 'FIXTURE';
const peer = thisScene.getLayer('late-image');
let baseline;
let frames = 0;
let propertyNotifications = 0;
export function applyUserProperties(properties) { propertyNotifications++; }
export function init(value) {
    if (thisScene.getLayer('missing') !== undefined || thisScene.getLayer(-1) !== undefined)
        throw new Error('missing scene layer');
    if (!thisScene.clearenabled || thisScene.bloom || Math.abs(thisScene.skylightcolor.x - .4) > .001 || Math.abs(thisScene.ambientcolor.x - .2) > .001)
        throw new Error('scene settings use wrong fields');
    thisScene.bloomstrength = 2.5;
    thisScene.bloomthreshold = .75;
    thisScene.skylightcolor = new Vec3(.6, .7, .8);
    thisScene.ambientcolor = new Vec3(.3, .2, .1);
    thisScene.clearcolor = new Vec3(.1, .2, .3);
    thisScene.clearenabled = false;
    if (thisScene.bloomstrength !== 2.5 || thisScene.bloomthreshold !== .75 || thisScene.clearenabled ||
        Math.abs(thisScene.skylightcolor.y - .7) > .001 || Math.abs(thisScene.ambientcolor.x - .3) > .001)
        throw new Error('scene setting write');
    thisScene.clearenabled = true;
    const screen = input.cursorScreenPosition;
    if (screen.x < 0 || screen.y < 0 || screen.x > engine.screenResolution.x || screen.y > engine.screenResolution.y)
        throw new Error('screen cursor bounds');
    if (token !== 17 || peer !== thisScene.getLayer(5)) throw new Error('module import/layer identity');
    peer.customValue = 7;
    localStorage.set('boolean', false, localStorage.LOCATION_SCREEN);
    if (localStorage.get('boolean', localStorage.LOCATION_SCREEN) !== false)
        throw new Error('storage value types');
    localStorage.delete('boolean', localStorage.LOCATION_SCREEN);
    const properties = createScriptProperties().addSlider({name:'defaultValue', value:3}).finish();
    if (properties.defaultValue !== 3) throw new Error('script-property default');
    if (!peer || thisLayer.scale.x !== 2 || Math.abs(thisLayer.angles.z - .25 * 180 / Math.PI) > .001 || !thisLayer.visible)
        throw new Error('typed image properties or deferred lookup');
    baseline = value;
    peer.alpha = .5;
    peer.origin = new Vec3(400, 240, 0);
    return value;
}
export function update(value) {
    if (propertyNotifications !== 1) throw new Error('repeated startup properties: ' + propertyNotifications);
    if (baseline.x !== 320 || baseline.y !== 240 || peer.alpha !== .5 || peer.origin.x !== 400 || peer.customValue !== 7)
        throw new Error('initial vector drift or cross-layer write');
    value.x = baseline.x + 10;
    if (++frames === 90) console.log('IMAGE_LIFECYCLE_PASS');
    return value;
}
export function destroy() {
    if (peer.alpha !== .5) throw new Error('destroy after layer deletion');
    console.log('IMAGE_DESTROY_PASS');
}
'''


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
    assert all(m in sizes for m in args.monitors), 'two connected outputs required'
    env = dict(os.environ, __GL_THREADED_OPTIMIZATIONS='0', LD_LIBRARY_PATH=str(binary.parent))
    env.pop('__GLX_VENDOR_LIBRARY_NAME', None)
    env.pop('EGL_PLATFORM', None)
    processes = []
    logs = []
    with tempfile.TemporaryDirectory(prefix='lwe-renderer-regression-') as directory:
        root = Path(directory)
        env['XDG_STATE_HOME'] = str(root / 'state')
        (root / 'scripts/jsmodules').mkdir(parents=True)
        (root / 'scripts/jsmodules/fixture.js').write_text('export const token = 17;')
        (root / 'materials').mkdir()
        (root / 'shaders').mkdir()
        (root / 'model.json').write_text(json.dumps({'material': 'material.json', 'width': 32, 'height': 32}))
        (root / 'material.json').write_text(json.dumps({'passes': [{'shader': 'copy', 'blending': 'normal',
                                                                  'textures': ['test']}]}))
        (root / 'shaders/copy.vert').write_text('''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}''')
        (root / 'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0; varying vec2 v_TexCoord;
void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord);}''')
        pixels = Image.new('RGBA', (32, 32), (240, 80, 40, 255)).tobytes()
        def integers(*values):
            return struct.pack('<' + 'I' * len(values), *values)
        (root / 'materials/test.tex').write_bytes(b'TEXV0005\0TEXI0001\0' + integers(0, 3, 32, 32, 32, 32, 0)
            + b'TEXB0002\0' + integers(1, 1, 32, 32, 0, len(pixels), len(pixels)) + pixels)
        (root / 'project.json').write_text(json.dumps({'title': 'Regression Test', 'type': 'scene',
                                                     'file': 'scene.json', 'general': {'properties': {}}}))
        (root / 'scene.json').write_text(json.dumps({
            'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
            'general': {'orthogonalprojection': {'width': 640, 'height': 480},
                        'clearcolor': '.1 .2 .3', 'ambientcolor': '.2 .2 .2', 'skylightcolor': '.4 .4 .4'},
            'objects': [{'id': 1, 'name': 'test', 'origin': '320 240 0', 'spacing': '12 6',
                         'text': {'value': 'Regression Test', 'script': SCRIPT}},
                        *[{'id': identifier, 'name': 'timer' + str(identifier), 'sound': [],
                           'origin': f'{identifier} 0 0',
                           'volume': {'value': 0, 'script': sound_timer_script(identifier)}}
                          for identifier in [2, 3]],
                        {'id': 4, 'name': 'script-image', 'image': 'model.json', 'size': '32 32',
                         'origin': {'value': '320 240 0', 'script': IMAGE_SCRIPT}, 'scale': '2 2 1',
                         'angles': '0 0 .25', 'visible': True},
                        {'id': 5, 'name': 'late-image', 'image': 'model.json', 'size': '32 32',
                         'origin': '450 240 0'}]}))

        def contents(index):
            return (root / f'{index}.log').read_text()

        def wait_for(predicate, message, timeout=30):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                for i, process in enumerate(processes):
                    assert process.poll() is None, contents(i)
                    assert 'VECTOR_FAIL' not in contents(i), contents(i)
                    assert 'SceneScript timer:' not in contents(i), contents(i)
                    assert 'ScriptEngine [' not in contents(i), contents(i)
                if predicate():
                    return
                time.sleep(.1)
            raise AssertionError(message + '\n' + '\n'.join(contents(i) for i in range(len(processes))))

        try:
            for i, monitor in enumerate(args.monitors):
                log = (root / f'{i}.log').open('w')
                logs.append(log)
                command = [str(binary), '--fps', '30', '--anti-aliasing', '2', '--silent', '--noautomute',
                           '--no-fullscreen-pause', '--layer', 'background', '--screen-root', monitor,
                           '--assets-dir', str(args.assets), '--control-file', str(root / f'{i}.json'),
                           '--screenshot', str(root / f'{i}.png'), '--screenshot-delay', '100', str(root)]
                processes.append(subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True))
            wait_for(lambda: all('VECTOR_PASS' in contents(i) for i in range(2)), 'native vector scripts')
            wait_for(lambda: all('TIMER_PASS' in contents(i) for i in range(2)), 'native timer ownership/cancellation')
            wait_for(lambda: all('TEXT_INIT_PASS' in contents(i) and 'IMAGE_LIFECYCLE_PASS' in contents(i)
                                for i in range(2)), 'deferred image/text lifecycle and stable vector baseline')
            wait_for(lambda: all(all(f'MODULE_TIMER_PASS {identifier}' in contents(i)
                                    for identifier in [2, 3]) for i in range(2)), 'per-script timer context')
            wait_for(lambda: all(all(f'DETACHED_AUDIO_PASS {identifier}' in contents(i)
                                    for identifier in [2, 3]) for i in range(2)), 'detached audio buffer handling')
            wait_for(lambda: all((root / f'{i}.png').exists() for i in range(2)), 'simultaneous render captures')
            for i, monitor in enumerate(args.monitors):
                with Image.open(root / f'{i}.png') as image:
                    assert image.size == sizes[monitor], (monitor, image.size, sizes[monitor])
                    assert image.getextrema()[0][1] > 200, 'text was not rendered'
                print('PASS native vectors, simultaneous output rendering', monitor, flush=True)
            for i, fps in enumerate([10, 60]):
                temporary = root / f'{i}.tmp'
                temporary.write_text(json.dumps({'fps': fps, 'volume': 0, 'scaling': 'stretch', 'alignment': [0,1]}))
                temporary.replace(root / f'{i}.json')
            time.sleep(4)
            for i, fps in enumerate([10, 60]):
                rates = [float(line.split('FRAME_RATE ', 1)[1]) for line in contents(i).splitlines() if 'FRAME_RATE ' in line]
                assert len(rates) >= 3, contents(i)
                assert abs(rates[-1] - fps) < fps * .2, (args.monitors[i], fps, rates)
                assert processes[i].poll() is None, 'live update restarted renderer'
                print('PASS live per-output FPS', args.monitors[i], round(rates[-1], 1), flush=True)
            # Frozen renderer must retain pending controls and apply them on resume.
            os.killpg(processes[0].pid, signal.SIGSTOP)
            (root / '0.json').write_text(json.dumps({'fps': 20}))
            os.killpg(processes[0].pid, signal.SIGCONT)
            time.sleep(3)
            rates = [float(line.split('FRAME_RATE ', 1)[1]) for line in contents(0).splitlines() if 'FRAME_RATE ' in line]
            assert abs(rates[-1] - 20) < 4, rates
            print('PASS controls applied after resume', flush=True)
        finally:
            for process in processes:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGCONT)
                    process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise
            for log in logs:
                log.close()
            assert all(p.returncode == 0 for p in processes), [p.returncode for p in processes]
            assert all('IMAGE_DESTROY_PASS' in contents(i) for i in range(2)), 'destroy lifecycle missing'


if __name__ == '__main__':
    main()
