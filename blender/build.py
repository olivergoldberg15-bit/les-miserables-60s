"""Headless entry point: assets -> world -> props -> actors -> shots."""
import faulthandler
import sys as _sys
faulthandler.enable(file=_sys.stderr, all_threads=True)  # print the Python stack if Blender segfaults
import argparse
import importlib
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from assets import Assets
from lib import Context


def arguments(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='build/lesmis.blend')
    parser.add_argument('--mode', choices=['lookdev', 'stills', 'full'], default='lookdev')
    parser.add_argument('--frames', default='1')
    parser.add_argument('--chunk', type=int, default=0)
    parser.add_argument('--chunks', type=int, default=20)
    parser.add_argument('--prepare-assets', action='store_true')
    return parser.parse_args(argv)


def build_modules(ctx):
    for name in ('world', 'props', 'actors', 'shots'):
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name != name:
                raise RuntimeError(f'[build:{name}] dependency missing: {exc.name}') from exc
            print(f'[build:{name}] missing module; skipped', flush=True)
            continue
        if not callable(getattr(module, 'build', None)):
            print(f'[build:{name}] no build(ctx); skipped', flush=True)
            continue
        try:
            module.build(ctx)
            # Keep whatever build(ctx) published (e.g. ctx.props = name -> object).
            if getattr(ctx, name, None) is None:
                setattr(ctx, name, module)
        except Exception as exc:
            raise RuntimeError(f'[build:{name}] {exc}') from exc


def main(args):
    import bpy
    random.seed(1815)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    assets = Assets()
    if args.prepare_assets:
        assets.prepare(include_people=(ROOT / 'blender/actors.py').exists())
    timing = json.loads((ROOT / 'data/timing.json').read_text(encoding='utf-8'))
    ctx = Context(timing=timing, args=args, assets=assets, collections={})
    scene = bpy.context.scene
    scene.render.fps = ctx.fps
    scene.frame_start = 1
    scene.frame_end = math.ceil(timing['duration'] * ctx.fps)
    scene['timing_json'] = json.dumps(timing)
    for name in ('ACTORS', 'PROPS', 'CAMERAS'):
        ctx.collections[name] = ctx.col(name)
    build_modules(ctx)
    world = getattr(ctx, 'world', None)
    scene['lookdev_cameras'] = json.dumps(getattr(world, 'LOOKDEV_CAMERAS', {}))
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print(f'[build] saved {out}', flush=True)


if __name__ == '__main__':
    main(arguments(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []))
