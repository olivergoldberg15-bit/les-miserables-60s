"""Render entry point; run after loading the saved .blend."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from assets import Assets
from lib import Context, look_at, set_time_of_day


def chunk_range(first, last, chunk, chunks):
    if not 1 <= chunks <= 100 or not 0 <= chunk < chunks:
        raise ValueError('[render] chunks must be 1..100; chunk must be 0..chunks-1')
    count = last - first + 1
    return first + count * chunk // chunks, first + count * (chunk + 1) // chunks - 1


def frame_list(spec):
    """Parse '1,240' or '302-392' (or a mix) into frame numbers."""
    frames = []
    for part in (value.strip() for value in spec.split(',')):
        if '-' in part:
            first, last = (int(v) for v in part.split('-'))
            frames.extend(range(first, last + 1))
        elif part:
            frames.append(int(part))
    return frames


def configure(scene, preview):
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    # Final: 32 adaptive samples + OIDN fits 1080p into GitHub's 6 h job limit (~3 min/frame).
    scene.cycles.samples = 24 if preview else 32
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .03 if preview else .04
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.max_bounces = 6 if preview else 4
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.seed = 1815
    scene.cycles.use_animated_seed = False
    scene.render.resolution_x = 960 if preview else 1920
    scene.render.resolution_y = 540 if preview else 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.use_motion_blur = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    for obj in scene.objects:
        if obj.type == 'CAMERA':
            obj.data.dof.use_dof = True


def lineup_objects(bpy):
    """Top-level objects of the ACTORS and PROPS collections, for the coordinator's review lineup."""
    found = {}
    for name in ('ACTORS', 'PROPS'):
        col = bpy.data.collections.get(name)
        if col:
            found[name] = [o for o in col.all_objects if o.parent is None]
    return {k: v for k, v in found.items() if v}


def render_lineup(bpy, scene, ctx, lineup, out):
    """Review still: actors in a row and props on a grid, far from the town, in neutral three-point light."""
    from mathutils import Vector
    base = Vector((0.0, -600.0, 0.0))
    roots = [bpy.data.collections[n] for n in ('ACTORS', 'PROPS') if n in bpy.data.collections]
    keep = {c.name for r in roots for c in [r, *r.children_recursive]}
    for col in bpy.data.collections:
        # Hide everything except ACTORS/PROPS, their descendants, and their ancestors.
        if col.name not in keep and not any(c.name in keep for c in col.children_recursive):
            col.hide_render = True
    for i, obj in enumerate(lineup.get('ACTORS', [])):
        obj.location = base + Vector(((i - (len(lineup['ACTORS']) - 1) / 2) * 1.3, 0.0, 0.0))
        obj.rotation_euler = (0.0, 0.0, 0.0)
    props = lineup.get('PROPS', [])
    for i, obj in enumerate(props):
        obj.location = base + Vector(((i % 6 - 2.5) * 0.45, -1.4 - (i // 6) * 0.45, 0.9))
    floor = bpy.data.objects.new('LINEUP_floor', bpy.data.meshes.new('LINEUP_floor'))
    floor.data.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
    floor.location = base
    scene.collection.objects.link(floor)
    for name, loc, energy, size in (('key', (-3, -6, 4), 900, 3), ('fill', (4, -5, 2), 250, 4), ('rim', (0, 4, 4), 700, 2)):
        light = bpy.data.objects.new('LINEUP_' + name, bpy.data.lights.new('LINEUP_' + name, 'AREA'))
        light.data.energy, light.data.size = energy, size
        light.location = base + Vector(loc)
        scene.collection.objects.link(light)
        look_at(light, base + Vector((0, 0, 1.0)))
    set_time_of_day(ctx, scene, 'interior_candle')
    for label, loc, target, lens in (('zz_actors_lineup', (0, -7.5, 1.5), (0, 0, 1.0), 40),
                                     ('zz_props_lineup', (0, -3.6, 1.6), (0, -1.6, 0.95), 50)):
        cam = bpy.data.objects.new('LOOKDEV_' + label, bpy.data.cameras.new('LOOKDEV_' + label))
        scene.collection.objects.link(cam)
        cam.location = base + Vector(loc)
        cam.data.lens = lens
        look_at(cam, base + Vector(target))
        scene.camera = cam
        scene.render.filepath = str(out / (label + '.png'))
        bpy.ops.render.render(write_still=True)


def main(args):
    import bpy
    scene = bpy.context.scene
    configure(scene, args.mode not in ('full', 'patch'))
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.mode == 'lookdev':
        cameras = json.loads(scene.get('lookdev_cameras', '{}'))
        ctx = Context(assets=Assets())
        lineup = lineup_objects(bpy)
        if not cameras and not lineup:
            raise RuntimeError('[render:lookdev] world.LOOKDEV_CAMERAS is empty and no ACTORS/PROPS exist; build world first')
        for name, spec in cameras.items():
            scene.frame_set(scene.frame_start)
            camera = bpy.data.objects.new('LOOKDEV_' + name, bpy.data.cameras.new('LOOKDEV_' + name))
            scene.collection.objects.link(camera)
            camera.location = spec['loc']
            camera.data.lens = spec['lens_mm']
            look_at(camera, spec['target'])
            from mathutils import Vector
            camera.data.dof.use_dof = True
            camera.data.dof.focus_distance = (Vector(spec['target']) - camera.location).length
            camera.data.dof.aperture_fstop = 5.6
            scene.camera = camera
            set_time_of_day(ctx, scene, spec['time'])
            scene.render.filepath = str(out / (name + '.png'))
            bpy.ops.render.render(write_still=True)
        if lineup:
            render_lineup(bpy, scene, ctx, lineup, out)
        return
    if args.mode in ('stills', 'patch'):
        frames = frame_list(args.frames)
        if not frames:
            raise ValueError(f'[render:{args.mode}] --frames must contain at least one frame')
        if any(frame < scene.frame_start or frame > scene.frame_end for frame in frames):
            raise ValueError(f'[render:{args.mode}] requested frame outside film')
        if args.mode == 'patch':
            # Final-quality re-render of the listed frames, split into contiguous chunks.
            first, last = chunk_range(0, len(frames) - 1, args.chunk, args.chunks)
            frames = frames[first:last + 1]
    else:
        start, end = chunk_range(scene.frame_start, scene.frame_end, args.chunk, args.chunks)
        frames = range(start, end + 1)
    for frame in frames:
        scene.frame_set(frame)
        if scene.camera is None:
            raise RuntimeError(f'[render] no camera at frame {frame}; shots module required')
        scene.render.filepath = str(out / f'{frame:06d}.png')
        bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['lookdev', 'stills', 'full', 'patch'], required=True)
    parser.add_argument('--frames', default='1')
    parser.add_argument('--chunk', type=int, default=0)
    parser.add_argument('--chunks', type=int, default=20)
    parser.add_argument('--out', default='build/frames')
    try:
        main(parser.parse_args(sys.argv[sys.argv.index('--') + 1:]))
    except Exception as exc:
        raise RuntimeError(f'[render] {exc}') from exc
