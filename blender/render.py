"""Render entry point; run after loading the saved .blend."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from assets import Assets
from lib import Context, look_at, set_time_of_day


def chunk_range(first, last, chunk, chunks):
    if not 1 <= chunks <= 20 or not 0 <= chunk < chunks:
        raise ValueError('[render] chunks must be 1..20; chunk must be 0..chunks-1')
    count = last - first + 1
    return first + count * chunk // chunks, first + count * (chunk + 1) // chunks - 1


def configure(scene, preview):
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 24 if preview else 96
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .03
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.max_bounces = 6
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


def main(args):
    import bpy
    scene = bpy.context.scene
    configure(scene, args.mode != 'full')
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.mode == 'lookdev':
        cameras = json.loads(scene.get('lookdev_cameras', '{}'))
        if not cameras:
            raise RuntimeError('[render:lookdev] world.LOOKDEV_CAMERAS is empty; build world first')
        ctx = Context(assets=Assets())
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
        return
    if args.mode == 'stills':
        frames = [int(value.strip()) for value in args.frames.split(',') if value.strip()]
        if not frames:
            raise ValueError('[render:stills] --frames must contain at least one frame')
        if any(frame < scene.frame_start or frame > scene.frame_end for frame in frames):
            raise ValueError('[render:stills] requested frame outside film')
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
    parser.add_argument('--mode', choices=['lookdev', 'stills', 'full'], required=True)
    parser.add_argument('--frames', default='1')
    parser.add_argument('--chunk', type=int, default=0)
    parser.add_argument('--chunks', type=int, default=20)
    parser.add_argument('--out', default='build/frames')
    try:
        main(parser.parse_args(sys.argv[sys.argv.index('--') + 1:]))
    except Exception as exc:
        raise RuntimeError(f'[render] {exc}') from exc
