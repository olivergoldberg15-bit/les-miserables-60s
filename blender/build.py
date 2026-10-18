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
    diagnose_animation(scene)
    world = getattr(ctx, 'world', None)
    scene['lookdev_cameras'] = json.dumps(getattr(world, 'LOOKDEV_CAMERAS', {}))
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print(f'[build] saved {out}', flush=True)


def diagnose_animation(scene):
    """Print why an actor would render in rest pose: NLA state, deform links, evaluated bones."""
    import bpy
    try:
        import actors
    except ImportError:
        return
    for name, actor in list(actors.ACTORS.items())[:2]:
        rig = actor.rig
        ad = rig.animation_data
        print(f'[diag] {name} rig={rig.name} type={rig.type} pose_position={rig.data.pose_position} '
              f'action={ad.action.name if ad and ad.action else None} tracks={len(ad.nla_tracks) if ad else 0} '
              f'use_nla={ad.use_nla if ad else None}', flush=True)
        for track in (ad.nla_tracks[:4] if ad else []):
            for strip in track.strips[:1]:
                curves = strip.action.fcurves if strip.action else []
                print(f'[diag]   track={track.name} mute={track.mute} strip={strip.frame_start:.0f}-{strip.frame_end:.0f} '
                      f'influence={strip.influence:.2f} mute={strip.mute} curves={len(curves)} '
                      f'first={curves[0].data_path if len(curves) else None}', flush=True)
        meshes = [o for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)
                  and (o.parent == rig or any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers))]
        others = {m.object.name if m.object else None for o in bpy.data.objects if o.type == 'MESH'
                  for m in o.modifiers if m.type == 'ARMATURE' and o.parent == rig}
        print(f'[diag]   deform meshes={len(meshes)} modifier objects={others}', flush=True)
        bone = next((b for b in rig.pose.bones if 'upperarm' in b.name.lower().replace(' ', '')), None)
        for frame in (300, 723):
            scene.frame_set(frame)
            if bone:
                print(f'[diag]   f{frame} {bone.name} quat={tuple(round(v, 3) for v in bone.rotation_quaternion)} '
                      f'mode={bone.rotation_mode} basis_angle={bone.matrix_basis.to_quaternion().angle:.3f}', flush=True)
        scene.frame_set(1006)
        for key in ('pelvis', 'head', 'lfoot', 'rfoot'):
            pb = next((x for x in rig.pose.bones if x.name.lower().replace(' ', '').endswith(key)), None)
            if pb:
                w = rig.matrix_world @ pb.head
                print(f'[diag]   f1006 {pb.name} world=({w.x:.2f},{w.y:.2f},{w.z:.2f})', flush=True)
        names = [b.name for b in rig.pose.bones][:6]
        print(f'[diag]   bones {names}', flush=True)


if __name__ == '__main__':
    main(arguments(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []))
