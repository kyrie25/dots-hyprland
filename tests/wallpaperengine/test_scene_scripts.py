"""Render layer creation/order/removal and camera controls with native SceneScript."""
import argparse
import json
import os
from pathlib import Path
import tempfile

from PIL import Image
from test_puppet_morph import render, u32


LIFECYCLE = '''const scene=thisScene; let ticks=0, parent, child;
export function init(value) {
    if(scene.enumerateLayers().length !== 1 || scene.getLayerIndex(thisLayer) !== 0)
        throw new Error('initial enumeration');
    for(const name of ['createLayer','enumerateLayers','destroyLayer','sortLayer','getLayerIndex','getLayer']) {
        let threw=false;
        try{scene[name].call({}, ... (name==='sortLayer' ? [thisLayer,0] : [thisLayer]));}
        catch(e){threw=e instanceof TypeError;}
        if(!threw) throw new Error('invalid receiver '+name);
    }
    const config=scene.getInitialLayerConfig(thisLayer);
    if('id' in config || config.image !== 'red.json') throw new Error('initial config');
    config.origin.value='0 0 0';
    if(scene.getInitialLayerConfig(thisLayer).origin.value !== '128 64 0') throw new Error('config alias');
    parent=scene.createLayer({name:'parent', image:'green.json', origin:new Vec3(128,64,0),
        alpha:{value:1, script:`export function init(v){ console.log('CREATED_INIT'); return .75; }
            export function applyUserProperties(){console.log('CREATED_PROPERTIES');}
            export function destroy(){console.log('CREATED_DESTROY');
                engine.setTimeout(()=>console.log('DEAD_TIMER'),0);}`}});
    if(parent.alpha !== .75) throw new Error('created module init must be synchronous');
    child=scene.createLayer({name:'child', parent:parent.id, image:'green.json', origin:new Vec3(0,0,0), visible:false});
    if(scene.enumerateLayers().length !== 3 || scene.getLayer('parent') !== parent)
        throw new Error('creation');
    if(!scene.sortLayer(parent,0) || scene.getLayerIndex(parent) !== 0) throw new Error('sort');
    console.log('SCENE_INIT_PASS'); return value;
}
export function update(value) {
    ++ticks;
    if(ticks === 20 && !scene.sortLayer(parent,2)) throw new Error('resort');
    if(ticks === 40) {
        if(!scene.destroyLayer(parent) || scene.destroyLayer(parent)) throw new Error('destroy request');
    }
    if(ticks === 45) {
        if(scene.enumerateLayers().length !== 1 || scene.getLayer('child') || scene.getLayerIndex(child) !== -1)
            throw new Error('parent/child cleanup');
        console.log('SCENE_CLEANUP_PASS');
    }
    return value;
}'''


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
    with tempfile.TemporaryDirectory(prefix='lwe-scene-scripts-') as directory:
        root = Path(directory)
        (root / 'materials').mkdir()
        (root / 'shaders').mkdir()
        (root / 'shaders/copy.vert').write_text('''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}''')
        (root / 'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0; uniform vec4 g_Color4;
varying vec2 v_TexCoord;void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord)*g_Color4;}''')
        def write(name, data):
            (root / name).write_text(json.dumps(data))
        write('project.json', {'title': 'Scene Scripts', 'type': 'scene', 'file': 'scene.json'})
        write('broken.json', {'material':'broken-material.json','width':64,'height':32})
        write('broken-material.json', {'passes':[{'shader':'missing-shader','textures':['red']}]})
        for name, color in [('red',(240,40,20)), ('green',(20,220,40))]:
            write(name+'.json', {'material': name+'-material.json', 'width':64, 'height':32})
            write(name+'-material.json', {'passes':[{'shader':'copy', 'blending':'translucent', 'textures':[name]}]})
            pixels=Image.new('RGBA',(64,32),(*color,255)).tobytes()
            (root / f'materials/{name}.tex').write_bytes(b'TEXV0005\0TEXI0001\0'+u32(0,3,64,32,64,32,0)
                +b'TEXB0002\0'+u32(1,1,64,32,0,len(pixels),len(pixels))+pixels)
        for name, script, delay, expected in [('before',LIFECYCLE,12,(240,40,20)),
                ('sorted',LIFECYCLE,30,(75,175,35)), ('removed',LIFECYCLE,60,(240,40,20)),
                ('zoom','export function init(v){thisScene.setCameraTransforms({zoom:2});return v;}',12,(240,40,20)),
                ('failed-create', '''export function init(v){
                    let failed=false;
                    try{thisScene.createLayer({image:'broken.json',
                        origin:{value:'128 64 0',script:"export function init(v){console.log('BAD_INIT');return v;}"}});}
                    catch(e){failed=true;}
                    if(!failed || thisScene.enumerateLayers().length!==1) throw new Error('failed creation cleanup');
                    console.log('FAILED_CREATE_PASS');return v;}''',12,(240,40,20)),
                ('cursor', '''let entered=false;
                    export function init(v){thisLayer.scale=new Vec3(4,4,1);return v;}
                    export function cursorEnter(e){
                        if(thisLayer.id!==1 || thisObject.id!==1 || !Number.isFinite(e.localPosition.x) ||
                            !Number.isFinite(e.worldPosition.y) || e.hitBox!==null) throw new Error('cursor payload');
                        entered=true; console.log('CURSOR_OWNER_PASS');
                    }
                    export function update(v){if(!entered) throw new Error('missing initial cursorEnter');return v;}''',12,(240,40,20)),
                ('translated','export function init(v){thisScene.setCameraTransforms({eye:new Vec3(20,0,0),center:new Vec3(20,0,-1)});return v;}',12,(240,40,20)),
                ('media-create', '''let events=0;
                    export function mediaPropertiesChanged(){
                        if(++events!==1) throw new Error('startup media replayed to creator');
                        console.log('MEDIA_CREATOR');
                        thisScene.createLayer({image:'green.json',visible:false,alpha:{value:1,script:
                            `let events=0;
                            export function mediaPropertiesChanged(){
                                if(++events!==1) throw new Error('startup media replayed to child');
                                console.log('MEDIA_CHILD');
                                thisScene.createLayer({image:'green.json',visible:false});
                            }`}});
                    }
                    export function update(v){
                        if(thisScene.enumerateLayers().length>3) throw new Error('unbounded media creation');
                        return v;
                    }''',60,(240,40,20))]:
            write('scene.json', {'camera':{'center':'0 0 -1','eye':'0 0 0','up':'0 1 0'},
                'general':{'orthogonalprojection':{'width':256,'height':128},'clearcolor':'0 0 0'},
                'objects':[{'id':1,'name':'base','image':'red.json','origin':{'value':'128 64 0','script':script}}]})
            image=render(root,binary,args,env,delay=delay)
            log=(root/'renderer.log').read_text()
            assert 'ScriptEngine [' not in log and 'SceneScript timer:' not in log,log
            bounds=image.getbbox()
            assert bounds,log
            pixel=image.getpixel(((bounds[0]+bounds[2])//2,(bounds[1]+bounds[3])//2))
            assert all(abs(a-b)<3 for a,b in zip(pixel,expected)),(name,pixel,expected,log)
            if name=='removed':
                assert 'SCENE_CLEANUP_PASS' in log and log.count('CREATED_DESTROY')==1 and 'DEAD_TIMER' not in log and log.count('CREATED_PROPERTIES')==1,log
            if name=='cursor': assert 'CURSOR_OWNER_PASS' in log,log
            if name=='failed-create': assert 'FAILED_CREATE_PASS' in log and 'BAD_INIT' not in log,log
            if name=='media-create': assert log.count('MEDIA_CREATOR')==1 and log.count('MEDIA_CHILD')==1,log
            if name=='before': baseline=bounds
            if name=='zoom': assert abs((bounds[2]-bounds[0])-2*(baseline[2]-baseline[0]))<=2,(bounds,baseline)
            if name=='translated': assert bounds[0]<baseline[0],(bounds,baseline)
            print('PASS scene scripts',name,pixel,bounds,flush=True)


if __name__=='__main__':
    main()
