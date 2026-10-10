"""Check forwarded desktop clicks, drag capture, expiry and disabled mouse input."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from PIL import Image
from test_puppet_morph import u32


SCRIPT = '''let frames=0;
export function update(value) {
    if (++frames % 5 === 0) {
        const p=input.cursorWorldPosition;
        console.log('INPUT_STATE '+p.x+' '+p.y+' '+input.cursorLeftDown);
    }
    return value;
}
export function cursorDown(e) { console.log('INPUT_DOWN'); }
export function cursorMove(e) { if(input.cursorLeftDown) console.log('INPUT_DRAG'); }
export function cursorUp(e) { console.log('INPUT_UP'); }
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--monitor', required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    screens = json.loads(subprocess.check_output(['hyprctl', '-j', 'monitors'], text=True))
    monitor = next(s for s in screens if s['name'] == args.monitor)
    original = json.loads(subprocess.check_output(['hyprctl', '-j', 'cursorpos'], text=True))
    env = dict(os.environ, LD_LIBRARY_PATH=str(binary.parent), DRI_PRIME='1',
               __GL_THREADED_OPTIMIZATIONS='0')
    env.pop('__GLX_VENDOR_LIBRARY_NAME', None)
    env.pop('EGL_PLATFORM', None)

    def move(x, y):
        subprocess.run(['hyprctl', 'eval', f'hl.dispatch(hl.dsp.cursor.move({{x={x},y={y}}}))'],
                       check=True, stdout=subprocess.DEVNULL)

    try:
        with tempfile.TemporaryDirectory(prefix='lwe-desktop-input-') as directory:
            root = Path(directory)
            (root / 'materials').mkdir()
            (root / 'project.json').write_text(json.dumps({'title':'Desktop Input Regression','type':'scene','file':'scene.json'}))
            (root / 'image.json').write_text(json.dumps({'material':'material.json','width':64,'height':32}))
            (root / 'material.json').write_text(json.dumps({'passes':[{'shader':'genericimage2',
                'blending':'normal','textures':['solid']}]}))
            pixels = Image.new('RGBA', (64,32), (30,220,80,255)).tobytes()
            (root / 'materials/solid.tex').write_bytes(b'TEXV0005\0TEXI0001\0'+u32(0,3,64,32,64,32,0)
                +b'TEXB0002\0'+u32(1,1,64,32,0,len(pixels),len(pixels))+pixels)
            (root / 'scene.json').write_text(json.dumps({'camera':{'center':'0 0 -1','eye':'0 0 0','up':'0 1 0'},
                'general':{'orthogonalprojection':{'width':256,'height':128}},
                'objects':[{'id':1,'name':'input-probe','image':'image.json','origin':{'value':'128 64 0','script':SCRIPT}}]}))
            input_file = root / 'input.json'

            def button(down):
                temporary = root / 'input.tmp'
                temporary.write_text(json.dumps({'leftDown':down}))
                temporary.replace(input_file)

            center = (monitor['x'] + monitor['width'] / monitor['scale'] / 2,
                      monitor['y'] + monitor['height'] / monitor['scale'] / 2)
            move(*center)
            for disabled in [False, True]:
                log_path = root / f'{disabled}.log'
                button(False)
                with log_path.open('w') as log:
                    process = subprocess.Popen([str(binary),'--fps','60','--silent','--noautomute',
                        '--no-fullscreen-pause','--anti-aliasing','0','--layer','background',
                        '--screen-root',args.monitor,'--assets-dir',str(args.assets),
                        '--input-file',str(input_file), *(['--disable-mouse'] if disabled else []),str(root)],
                        env=env,stdout=log,stderr=log,start_new_session=True)
                    def expect(predicate):
                        deadline=time.monotonic()+15
                        while time.monotonic()<deadline:
                            text=log_path.read_text()
                            assert process.poll() is None,text
                            if predicate(text): return text
                            time.sleep(.05)
                        raise AssertionError(log_path.read_text())
                    try:
                        expect(lambda t:'INPUT_STATE' in t)
                        button(True)
                        if disabled:
                            time.sleep(.4)
                            text=log_path.read_text()
                            assert 'INPUT_DOWN' not in text and ' true' not in text,text
                        else:
                            expect(lambda t:'INPUT_DOWN' in t)
                            move(center[0]+monitor['width']/monitor['scale']/4,center[1])
                            expect(lambda t:'INPUT_DRAG' in t)
                            button(False)
                            expect(lambda t:'INPUT_UP' in t)
                            move(*center)
                            button(True)
                            expect(lambda t:t.count('INPUT_DOWN')>=2)
                            # A lost shell must release its last held button without a restart.
                            os.utime(input_file,(time.time()-3,time.time()-3))
                            expect(lambda t:t.count('INPUT_UP')>=2)
                            button(True)
                            expect(lambda t:t.count('INPUT_DOWN')>=3)
                            input_file.write_text('{')
                            expect(lambda t:t.count('INPUT_UP')>=3)
                    finally:
                        process.terminate()
                        process.wait(timeout=10)
                    assert process.returncode==0,log_path.read_text()
                print('PASS disabled input' if disabled else 'PASS cursor, forwarded clicks, drag, expiry and invalid input')
    finally:
        move(original['x'], original['y'])


if __name__ == '__main__':
    main()
