"""Verify native puppet controls and that bone script writes reach rendered geometry."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from PIL import Image
from test_puppet_morph import puppet, render, u32


CHECKS = r'''
let ticks = 0;
let initial;
export function init(value) {
    if (thisLayer.getBoneCount() !== 1 || thisLayer.getBoneIndex('root') !== 0 ||
        thisLayer.getBoneParentIndex('root') !== -1 || thisLayer.getBoneIndex('missing') !== -1)
        throw new Error('bone lookup');
    const animation = thisLayer.getAnimationLayer(0);
    if (animation !== thisLayer.getAnimationLayer(0) || thisLayer.getAnimationLayerCount() !== 1 ||
        animation.fps !== 1 || animation.frameCount !== 1 || animation.duration !== 1)
        throw new Error('animation identity/metadata');
    animation.pause();
    animation.setFrame(.5);
    if (animation.isPlaying() || Math.abs(animation.getFrame() - .5) > .001)
        throw new Error('animation pause/seek');
    animation.play();
    if (!animation.isPlaying()) throw new Error('animation play');
    animation.stop();
    if (animation.isPlaying() || animation.getFrame() !== 0) throw new Error('animation stop');
    animation.rate = .5;
    animation.blend = .75;
    animation.visible = false;
    if (animation.rate !== .5 || animation.blend !== .75 || animation.visible)
        throw new Error('animation properties: ' + animation.rate + '/' + animation.blend + '/' + animation.visible);
    const created = thisLayer.createAnimationLayer('test', {name:'created', visible:false, blendin:false});
    if (!created || created !== thisLayer.getAnimationLayer('created') || thisLayer.getAnimationLayerCount() !== 2)
        throw new Error('animation creation');
    if (!thisLayer.destroyAnimationLayer(created) || created.isPlaying() ||
        thisLayer.destroyAnimationLayer(created) || thisLayer.getAnimationLayerCount() !== 1)
        throw new Error('animation destroyed handle');
    const single = thisLayer.playSingleAnimation('test', {name:'single', visible:true, blendin:false, blendout:false});
    single.addEndedCallback(function() {
        if (thisLayer.id !== 1 || this !== single) throw new Error('animation callback owner');
        console.log('ANIMATION_ENDED_PASS');
    });
    initial = value;
    console.log('PUPPET_CONTROLS_PASS');
    return value;
}
export function update(value) {
    if (initial.x !== 128) throw new Error('retained puppet baseline drift');
    BODY
    if (++ticks === 70) console.log('PUPPET_BONE_PASS');
    return value;
}
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
    with tempfile.TemporaryDirectory(prefix='lwe-puppet-scripts-') as directory:
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
        write('project.json', {'title': 'Puppet Scripts', 'type': 'scene', 'file': 'scene.json'})
        write('model.json', {'material': 'material.json', 'puppet': 'test.mdl', 'width': 64, 'height': 32})
        write('material.json', {'passes': [{'shader': 'copy', 'blending': 'normal', 'textures': ['test']}]})
        (root / 'test.mdl').write_bytes(puppet(morph_weight=0).replace(b'loop\0', b'single\0'))
        # Replacing the clip mode changes its section end; zero means through EOF.
        data = bytearray((root / 'test.mdl').read_bytes())
        offset = data.index(b'MDLA0004\0') + len(b'MDLA0004\0')
        data[offset:offset+4] = u32(len(data))
        (root / 'test.mdl').write_bytes(data)
        pixels = Image.new('RGBA', (64, 32), (240, 80, 40, 255)).tobytes()
        (root / 'materials/test.tex').write_bytes(b'TEXV0005\0TEXI0001\0' + u32(0, 3, 64, 32, 64, 32, 0)
            + b'TEXB0002\0' + u32(1, 1, 64, 32, 0, len(pixels), len(pixels)) + pixels)
        baseline = None
        for name, body in [
            ('baseline', ''),
            ('origin', "thisLayer.setLocalBoneOrigin('root', new Vec3(20,0,0));"),
            ('local-matrix', "let m=thisLayer.getLocalBoneTransform(0); m.m[12]=20; thisLayer.setLocalBoneTransform(0,m);"),
            ('world-matrix', "let m=thisLayer.getBoneTransform(0); m.m[12]+=20; thisLayer.setBoneTransform(0,m);"),
            ('angles', "thisLayer.setLocalBoneAngles(0,new Vec3(0,0,Math.PI/2));"),
        ]:
            write('scene.json', {'camera': {'center': '0 0 -1', 'eye': '0 0 0', 'up': '0 1 0'},
                'general': {'orthogonalprojection': {'width': 256, 'height': 128}, 'clearcolor': '0 0 0'},
                'objects': [{'id': 1, 'name': 'puppet', 'image': 'model.json',
                    'origin': {'value': '128 64 0', 'script': CHECKS.replace('BODY', body)},
                    'animationlayers': [{'animation': 42, 'visible': True, 'blend': 1}]}]})
            image = render(root, binary, args, env, delay=90)
            log = (root / 'renderer.log').read_text()
            assert 'ScriptEngine [' not in log and 'PUPPET_CONTROLS_PASS' in log and 'PUPPET_BONE_PASS' in log, log
            assert 'ANIMATION_ENDED_PASS' in log, log
            bounds = image.getbbox()
            if name == 'baseline':
                baseline = bounds
            elif name == 'angles':
                assert abs((bounds[2]-bounds[0]) - (baseline[3]-baseline[1])) < 3, (name,bounds,baseline)
            else:
                displacement = 20 * image.width / 256
                assert abs(bounds[0] - baseline[0] - displacement) < 3, (name,bounds,baseline)
            print('PASS puppet scripts', name, flush=True)


if __name__ == '__main__':
    main()
