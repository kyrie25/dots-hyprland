"""Render the native second-mesh texture-channel path, including malformed optional data."""
import argparse
import json
import os
from pathlib import Path
import struct
import tempfile

from PIL import Image
from test_puppet_morph import f32, render, u32


def puppet_channels(weight, rows=1, index=0, padded=False):
    mask=0x01800009
    data=b'MDLV0021\0'+u32(mask,1,2)
    vertices=b''
    for x,y,u,v in [(-32,-16,0,0),(32,-16,1,0),(-32,16,0,1),(32,16,1,1)]:
        vertices+=f32(x,y,0)+u32(0,0,0,0)+f32(1,0,0,0,u,v)
    data+=b'material.json\0'+u32(0)+f32(-32,-16,0,32,16,0)+u32(mask,len(vertices))+vertices
    data+=u32(12)+struct.pack('<6H',0,1,2,2,1,3)+b'\0\0'
    mask=0x00800021
    vertices=b''
    for x,y,u,v in [(16,8,0,0),(48,8,1,0),(16,24,0,1),(48,24,1,1)]:
        vertices+=f32(x,y,0)+u32(index,0,0,0)+f32(u*(.5 if padded else 1),v*(.5 if padded else 1),u,v)
    data+=b'channel.json\0'+u32(2,rows)+f32(16,8,0,48,24,0)+u32(mask,len(vertices))+vertices
    data+=u32(12)+struct.pack('<6H',0,1,2,2,1,3)+b'\0\0'
    identity=f32(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)
    skeleton=u32(1)+b'root\0'+u32(0,0xffffffff,64)+identity+b'\0'
    clip=u32(1)+struct.pack('<Q',42)+b'channel\0loop\0'+f32(1)+u32(1,0,1)
    clip+=u32(0,72)+f32(*([0,0,0,0,0,0,1,1,1]*2))
    clip+=u32(index+1)
    for lane in range(index+1):
        clip+=u32(0,8)+f32(weight if lane==index else 0, weight if lane==index else 0)
    clip+=b'\0\0'+u32(0)
    for tag,payload in [(b'MDLS0001\0',skeleton),(b'MDLA0004\0',clip)]:
        data+=tag+u32(len(data)+len(tag)+4+len(payload))+payload
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--monitor',required=True)
    args=parser.parse_args()
    binary=args.binary.resolve()
    env=dict(os.environ,LD_LIBRARY_PATH=str(binary.parent),__GL_THREADED_OPTIMIZATIONS='0')
    env.pop('__GLX_VENDOR_LIBRARY_NAME',None)
    env.pop('EGL_PLATFORM',None)
    with tempfile.TemporaryDirectory(prefix='lwe-puppet-channels-') as directory:
        root=Path(directory)
        (root/'materials').mkdir()
        (root/'shaders').mkdir()
        (root/'shaders/copy.vert').write_text('''uniform mat4 g_ModelViewProjectionMatrix;
attribute vec3 a_Position; attribute vec2 a_TexCoord; varying vec2 v_TexCoord;
void main(){v_TexCoord=a_TexCoord;gl_Position=g_ModelViewProjectionMatrix*vec4(a_Position,1.0);}''')
        (root/'shaders/copy.frag').write_text('''uniform sampler2D g_Texture0; uniform vec4 g_Color4;
varying vec2 v_TexCoord;void main(){gl_FragColor=texSample2D(g_Texture0,v_TexCoord)*g_Color4;}''')
        def write(name,data):
            (root/name).write_text(json.dumps(data))
        write('project.json',{'title':'Channels','type':'scene','file':'scene.json'})
        write('model.json',{'material':'material.json','puppet':'test.mdl','width':64,'height':32})
        write('effect.json',{'name':'Copy','passes':[{'material':'copy.json'}]})
        write('copy.json',{'passes':[{'shader':'copy','blending':'normal'}]})
        baseline={}
        for route in ['direct','prepass','doublebuffered']:
            for effects in [False,True]:
                for weight,rows,index,padded in [(0,1,0,False),(.5,1,0,False),(1,1,0,False),(1,2,5,False),(1,0,0,False),(1,1,4,False),(0,1,0,True),(1,1,0,True)]:
                    for name,color in [('base',(240,40,20)),('channel',(20,220,40))]:
                        size=(128,64) if padded else (64,32)
                        texture=Image.new('RGBA',size)
                        texture.paste((*color,255),(0,0,64,32))
                        if name=='base': texture.paste((40,20,240,255),(0,0,64,4))
                        pixels=texture.tobytes()
                        (root/f'materials/{name}.tex').write_bytes(b'TEXV0005\0TEXI0001\0'+u32(0,3,*size,64,32,0)
                            +b'TEXB0002\0'+u32(1,1,*size,0,len(pixels),len(pixels))+pixels)
                    write('material.json',{'passes':[{'shader':'copy','blending':'normal','textures':['base'],
                        'combos':{'LIGHTING':1} if route=='prepass' else {}}]})
                    write('channel.json',{'passes':[{'shader':'puppettexturechannels','blending':'translucent',
                        'textures':['channel','base'] if route=='doublebuffered' else ['channel'],
                        'combos':{'BLENDROWCOUNT':rows, 'DOUBLEBUFFERED':int(route=='doublebuffered')}}]})
                    (root/'test.mdl').write_bytes(puppet_channels(weight,rows,index,padded))
                    write('scene.json',{'camera':{'center':'0 0 -1','eye':'0 0 0','up':'0 1 0'},
                        'general':{'orthogonalprojection':{'width':256,'height':128},'clearcolor':'0 0 0'},
                        'objects':[{'id':1,'name':'puppet','image':'model.json','origin':'128 64 0',
                            'animationlayers':[{'animation':42,'visible':True,'blend':1}],
                            'effects':[{'file':'effect.json'}] if effects else []}]})
                    image=render(root,binary,args,env)
                    log=(root/'renderer.log').read_text()
                    valid=rows>0 and index<rows*4
                    assert ('Ignoring puppet texture channels:' in log)==(not valid),log
                    assert 'Could not load puppet mesh' not in log,log
                    pixel=image.getpixel((image.width//2,image.height//2))
                    blend=weight if valid else 0
                    expected=tuple(round(a*(1-blend)+b*blend) for a,b in zip((240,40,20),(20,220,40)))
                    assert all(abs(a-b)<3 for a,b in zip(pixel,expected)),(route,effects,weight,rows,index,pixel,expected,log)
                    if weight==0:
                        if route=='direct': baseline[effects,padded]=image
                        else:
                            from PIL import ImageChops
                            difference=ImageChops.difference(image,baseline[effects,padded])
                            assert max(hi for lo,hi in difference.getextrema())<4,(route,effects,padded,'source orientation/bounds',difference.getbbox(),log)
                    print('PASS channels',route,effects,weight,rows,index,padded,pixel,flush=True)


if __name__=='__main__':
    main()
