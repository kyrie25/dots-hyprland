"""Check actual Wayland presentation with grim, rather than an internal FBO.

Requires a running Wayland session, grim and Pillow. A temporary top-layer green
wallpaper covers the selected monitor during the check and is removed afterward.
EGL vendor selection is inherited, so callers can test explicit vendors as well.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from PIL import Image
from test_puppet_morph import u32


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--monitor', required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    env = dict(os.environ, LD_LIBRARY_PATH=str(binary.parent),
               __GL_THREADED_OPTIMIZATIONS='0')
    env.pop('__GLX_VENDOR_LIBRARY_NAME', None)
    with tempfile.TemporaryDirectory(prefix='lwe-presentation-') as directory:
        root = Path(directory)
        (root / 'materials').mkdir()
        (root / 'project.json').write_text(json.dumps({
            'title':'Presentation Regression', 'type':'scene', 'file':'scene.json'}))
        (root / 'image.json').write_text(json.dumps({
            'material':'material.json', 'width':256, 'height':128}))
        (root / 'material.json').write_text(json.dumps({'passes':[{
            'shader':'genericimage2', 'blending':'normal', 'textures':['solid']}]}))
        pixels = Image.new('RGBA', (256,128), (30,220,80,255)).tobytes()
        (root / 'materials/solid.tex').write_bytes(
            b'TEXV0005\0TEXI0001\0' + u32(0,3,256,128,256,128,0)
            + b'TEXB0002\0' + u32(1,1,256,128,0,len(pixels),len(pixels)) + pixels)
        (root / 'scene.json').write_text(json.dumps({
            'camera':{'center':'0 0 -1', 'eye':'0 0 0', 'up':'0 1 0'},
            'general':{'orthogonalprojection':{'width':256, 'height':128}},
            'objects':[{'id':1, 'name':'presentation-probe', 'image':'image.json',
                        'origin':'128 64 0'}]}))
        with (root / 'renderer.log').open('w') as log:
            process = subprocess.Popen([
                str(binary), '--fps','30', '--silent', '--noautomute',
                '--no-fullscreen-pause', '--anti-aliasing','0', '--layer','top',
                '--screen-root',args.monitor, '--assets-dir',str(args.assets),
                str(root)], env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                deadline = time.monotonic() + 15
                green = total = 0
                while time.monotonic() < deadline:
                    assert process.poll() is None, (root / 'renderer.log').read_text()
                    subprocess.run(['grim','-o',args.monitor,str(root / 'screen.png')],
                                   check=True, stdout=subprocess.DEVNULL)
                    with Image.open(root / 'screen.png') as capture:
                        rgb = capture.convert('RGB').tobytes()
                    total = len(rgb) // 3
                    green = sum(r < 60 and g > 180 and b < 110
                                for r,g,b in zip(rgb[::3],rgb[1::3],rgb[2::3]))
                    if green > total * .9:
                        print(f'PASS compositor presentation on {args.monitor}: {green}/{total} pixels')
                        return
                    time.sleep(.2)
                raise AssertionError((f'Compositor received {green}/{total} green pixels',
                                      (root / 'renderer.log').read_text()))
            finally:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
