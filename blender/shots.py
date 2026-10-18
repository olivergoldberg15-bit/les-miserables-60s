"""Cue-driven film edit. Run by build.py in Blender 4.2, never standalone.

Root motion is in-place Rocketbox plus keyed world-space blocking. Visibility
is baked onto objects (Collection.hide_render is not animatable in Blender).
No frame handlers: random-access chunk renders evaluate the same saved curves.
"""
import math
import random
import bpy
from mathutils import Vector
import lib
import actors
from world import LOCATIONS, LOOKDEV_CAMERAS

PREVIEW_FRAMES = {}
SHOT_IDS = ('open', 'bread', 'years', 'passport', 'rejected', 'bishop',
            'door', 'dinner', 'night', 'bedside', 'steal', 'caught', 'cliff')


def walk(col):
    """Objects in a collection tree, walked directly. The cached recursive object
    list can dangle after clip imports are deleted and segfault Blender 4.2."""
    seen = set()
    for c in (col, *col.children_recursive):
        for obj in c.objects:
            if obj.name not in seen:
                seen.add(obj.name)
                yield obj


def key(obj, path, value, frame, constant=False):
    setattr(obj, path, value)
    obj.keyframe_insert(data_path=path, frame=frame)
    # Node sockets store their animation on their owning node tree.
    owner = obj.id_data
    action = owner.animation_data.action if owner.animation_data else None
    if action:
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                if point.co.x == frame:
                    point.interpolation = 'CONSTANT' if constant else 'BEZIER'
                    point.handle_left_type = point.handle_right_type = 'AUTO_CLAMPED'


def visible(obj, start, end):
    key(obj, 'hide_render', True, 1, True)
    key(obj, 'hide_render', False, start, True)
    key(obj, 'hide_render', True, end + 1, True)


def tree(root):
    return [root, *root.children_recursive]


def build(ctx):
    scene = bpy.context.scene
    ranges = {s: ctx.shot_range(s) for s in SHOT_IDS}
    PREVIEW_FRAMES.clear()
    PREVIEW_FRAMES.update({s: (a+b)//2 for s, (a, b) in ranges.items()})
    cue = lambda s, w: ctx.frame(ctx.cue(s, w))
    def word_end(s, w):
        # cue validates the spelling; word end must come from the same record.
        ctx.cue(s, w)
        return ctx.frame(next(v['e'] for line in ctx.timing['lines'] if line['id'] == s
                              for v in line['words'] if lib.normalized(v['w']) == lib.normalized(w)))
    cut = word_end('cliff', 'says')
    cams = ctx.col('CAMERAS')
    lights = ctx.col('SHOT_LIGHTS')
    rng = random.Random(1815)

    def camera(name, place, a, b, loc=None, target=None, lens=None, end_loc=None, end_target=None):
        spec = LOOKDEV_CAMERAS[place]
        loc, target = Vector(loc or spec['loc']), Vector(target or spec['target'])
        data = bpy.data.cameras.new('CAM_' + name)
        obj = bpy.data.objects.new(data.name, data)
        cams.objects.link(obj)
        data.lens = lens or spec['lens_mm']
        data.clip_start, data.clip_end = .05, 1000
        data.dof.use_dof, data.dof.aperture_fstop = True, 4
        focus = bpy.data.objects.new('FOCUS_' + name, None)
        cams.objects.link(focus)
        data.dof.focus_object = focus
        finish = Vector(end_loc) if end_loc else loc + (target-loc).normalized() * .25
        aim_end = Vector(end_target) if end_target else target
        # Slow physical move with deterministic 1-2 cm handheld drift.
        for i in range(9):
            t = i/8
            f = a + (b-a)*t
            drift = Vector(tuple(rng.uniform(-.012, .012) for _ in range(3))) if i not in (0, 8) else Vector((0, 0, 0))
            obj.location = loc.lerp(finish, t) + drift
            focus.location = target.lerp(aim_end, t)
            lib.look_at(obj, focus.location)
            for path in ('location', 'rotation_euler'):
                key(obj, path, getattr(obj, path).copy(), f)
            key(focus, 'location', focus.location.copy(), f)
        marker = scene.timeline_markers.new(name, frame=a)
        marker.camera = obj
        if a == 1:
            scene.camera = obj
        return obj

    def light(name, loc, target, a, b, energy=120, color=(1, .48, .18), size=.4):
        data = bpy.data.lights.new(name, 'AREA')
        obj = bpy.data.objects.new(name, data)
        lights.objects.link(obj)
        obj.location = loc
        data.energy, data.color, data.shape, data.size = energy, color, 'DISK', size
        lib.look_at(obj, target)
        visible(obj, a, b)
        return obj

    def block(name, loc, a, b, clip='idle', rot=0, points=None, pose=None):
        root = actors.place(name, loc, rot)
        if root.animation_data and root.animation_data.action:
            for curve in root.animation_data.action.fcurves:
                if curve.keyframe_points:
                    curve.keyframe_points[-1].interpolation = 'CONSTANT'
        # Constant placement keys prevent travel through other shots.
        key(root, 'location', tuple(loc), a, True)
        key(root, 'rotation_euler', (0, 0, rot), a, True)
        if points:
            actors.move_along(name, points, a, b)
            key(root, 'location', tuple(points[-1]), b, True)
        if pose:
            actors.pose(name, pose, a, b)
        else:
            strip = actors.play(name, clip, a, loop=True)
            strip.frame_end = b + 1
        return root

    def half(name, loc, a, b, color=(1, .48, .18)):
        # Evaluate the current blocking before the public head-following helper.
        scene.frame_set(a)
        lamp = light('KEY_%s_%s' % (name, a), (loc[0]+1.4, loc[1]-.2, loc[2]+2.1),
                     (loc[0], loc[1], loc[2]+1.5), a, b, 65, color, .22)
        flag = actors.face_light(name, lamp)
        for path in ('location', 'rotation_euler', 'scale'):
            value = getattr(flag, path).copy()
            key(flag, path, value, a, True)
            key(flag, path, value, b, True)
        # Flag visibility is managed with its actor collection below.

    def prop(name, loc, frame, rot=None):
        obj = ctx.props[name]
        key(obj, 'location', tuple(loc), frame, True)
        if rot is not None:
            key(obj, 'rotation_euler', rot, frame, True)
        return obj

    # Bake preset HDRIs into an animatable world shader. World pointers and image
    # pointers cannot be keyframed, whereas shader socket values can.
    master = bpy.data.worlds.new('FILM_WORLD')
    master.use_nodes = True
    nodes, links = master.node_tree.nodes, master.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputWorld')
    previous = nodes.new('ShaderNodeBackground')
    previous.inputs['Color'].default_value = (0, 0, 0, 1)
    previous.inputs['Strength'].default_value = 0
    policies = {'open': 'dusk', 'bread': 'night', 'years': 'interior_moon',
                'passport': 'dusk', 'rejected': 'dusk', 'bishop': 'interior_candle',
                'door': 'night', 'dinner': 'interior_candle', 'night': 'interior_moon',
                'bedside': 'interior_moon', 'steal': 'interior_moon', 'caught': 'dawn', 'cliff': 'dawn'}
    for sid in SHOT_IDS:
        a, b = ranges[sid]
        b = min(b, cut-1)
        preset = lib.set_time_of_day(ctx, scene, policies[sid])
        env = nodes.new('ShaderNodeTexEnvironment')
        env.image = preset.node_tree.nodes['Environment'].image
        bg = nodes.new('ShaderNodeBackground')
        bg.inputs['Strength'].default_value = preset.node_tree.nodes['Background'].inputs['Strength'].default_value
        links.new(env.outputs['Color'], bg.inputs['Color'])
        mix = nodes.new('ShaderNodeMixShader')
        links.new(previous.outputs[0], mix.inputs[1])
        links.new(bg.outputs[0], mix.inputs[2])
        for f, value in ((1, 0), (a, 1), (b+1, 0)):
            key(mix.inputs[0], 'default_value', value, f, True)
        previous = mix
        sun = bpy.data.objects['TIME_SUN']
        for path in ('energy', 'color'):
            key(sun.data, path, getattr(sun.data, path), a, True)
        key(scene.view_settings, 'exposure', scene.view_settings.exposure, a, True)
    links.new(previous.outputs[0], output.inputs['Surface'])
    scene.world = master

    a, b = ranges['open']
    # Cover a believable short road segment, rather than sprinting 120m in 7s.
    block('valjean', (-83, -15, .35), a, b, 'walk_weary', rot=-.98,
          points=[(-83, -15, .35), (-76, -11, .12)])
    camera('open', 'road', a, b, end_loc=(-81, -15, 2.1), end_target=(-74, -9, 1.3), lens=32)
    half('valjean', (-83, -15, .35), a, b)

    a, b = ranges['bread']
    camera('bread', 'bakery_flashback', a, b, lens=50)
    block('valjean', (-240, 85, 0), a, b, 'knock', rot=math.pi)
    loaf = prop('bakery_loaf', LOCATIONS['bakery_flashback']['anchors']['loaf'], a)
    take = cue('bread', 'loaf')
    key(loaf, 'location', (-240, 86.4, 1.2), take)
    key(loaf, 'location', (-240, 85.2, 1.25), word_end('bread', 'bread'))
    for obj in walk(ctx.col('bakery_flashback')):
        if obj.get('breakable'):
            key(obj, 'hide_render', False, a, True)
            key(obj, 'hide_render', True, cue('bread', 'stole'), True)

    a, b = ranges['years']
    camera('years', 'galley_flashback', a, b, end_loc=(-237.7, 122, 1.6))
    block('valjean', (-241.8, 124.5, 0), a, b, 'crouch_idle', rot=-math.pi/2)
    prop('iron_chain', (-242.5, 124.7, 1), a)
    light('GALLEY_WINDOW', (-240, 128.5, 2.5), (-242, 124, 1), a, b, 160, (.4, .55, 1), .5)

    a, b = ranges['passport']
    block('valjean', (-51, -5, 0), a, b, 'idle_nervous')
    prop('yellow_passport', (-51, -5.35, 1.12), a, (math.radians(55), 0, 0))
    camera('passport', 'main_street', a, b, loc=(-50.8, -6.1, 1.55), target=(-51, -5.35, 1.15), lens=65)
    half('valjean', (-51, -5, 0), a, b)

    a, b = ranges['rejected']
    prison, kennel = cue('rejected', 'prison'), cue('rejected', 'kennel')
    camera('rejected_inn', 'main_street', a, prison-1, loc=(-43, -4, 1.6), target=(-45, 0, 1.2), lens=35)
    camera('rejected_prison', 'prison', prison, kennel-1,
           loc=(-22.7, 1.5, 1.7), target=(-25, -2.4, 1.2), lens=35)
    camera('rejected_kennel', 'kennel', kennel, b,
           loc=(-14, 3, 1.6), target=(-12, 6.1, .95), lens=32)
    # Dusk falls to night at the prison cut; all values come from the preset.
    night_world = lib.set_time_of_day(ctx, scene, 'night')
    rejected_bg = nodes.new('ShaderNodeBackground')
    rejected_env = nodes.new('ShaderNodeTexEnvironment')
    rejected_env.image = night_world.node_tree.nodes['Environment'].image
    links.new(rejected_env.outputs['Color'], rejected_bg.inputs['Color'])
    rejected_bg.inputs['Strength'].default_value = night_world.node_tree.nodes['Background'].inputs['Strength'].default_value
    night_mix = nodes.new('ShaderNodeMixShader')
    links.new(previous.outputs[0], night_mix.inputs[1])
    links.new(rejected_bg.outputs[0], night_mix.inputs[2])
    for f, value in ((1, 0), (prison, 1), (b+1, 0)):
        key(night_mix.inputs[0], 'default_value', value, f, True)
    links.new(night_mix.outputs[0], output.inputs['Surface'])
    sun = bpy.data.objects['TIME_SUN']
    for path in ('energy', 'color'):
        key(sun.data, path, getattr(sun.data, path), prison, True)
    key(scene.view_settings, 'exposure', scene.view_settings.exposure, prison, True)
    scene.world = master
    block('valjean', (-45, -1, 0), a, prison-1, 'idle_nervous', rot=math.pi)
    block('valjean', (-25, -1.8, 0), prison, kennel-1, 'idle_nervous', rot=0)
    block('valjean', (-12, 5.1, 0), kennel, b, 'idle_nervous', rot=math.pi,
          points=[(-12, 5.1, 0), (-12, 4.4, 0)])
    door = bpy.data.objects['inn_door']
    key(door, 'rotation_euler', (0, 0, -1.1), a, True)
    key(door, 'rotation_euler', (0, 0, 0), word_end('rejected', 'Inns'))
    spill = light('INN_SPILL', (-45, .5, 2), (-45, -2, .5), a, prison-1, 90)
    key(spill.data, 'energy', 90, cue('rejected', 'Inns'))
    key(spill.data, 'energy', 8, word_end('rejected', 'Inns'))
    light('INN_LANTERN_POOL', (-43.7, -1.2, 2.6), (-45, -1, 1), a, prison-1, 140)
    light('PRISON_LANTERN_POOL', (-23.5, -.9, 2.6), (-25, -2, 1), prison, kennel-1,
          160, (1, .55, .25), .3)
    light('KENNEL_SUBJECT_MOON', (-10.2, 4.8, 3.6), (-12, 5, 1), kennel, b,
          160, (.38, .53, 1), .6)
    wicket = bpy.data.objects['prison_wicket']
    key(wicket, 'location', (-24.45, -2.86, 1.52), a, True)
    key(wicket, 'location', (-25, -2.86, 1.52), word_end('rejected', 'prison'))
    light('KENNEL_GLINT', (-12, 5.8, .6), LOCATIONS['kennel']['anchors']['eyes'],
          cue('rejected', 'kennel'), b, 3, (.7, .8, 1), .05)

    a, b = ranges['bishop']
    exterior = cue('bishop', 'never')
    camera('bishop_fire', 'dining_room', a, exterior-1, lens=35)
    camera('bishop_unlocked', 'bishop_house', exterior, b, lens=35)
    block('bishop', (55.6, -2.9, 0), a, b, 'sit_chair_idle', rot=-math.pi/2)
    half('bishop', (55.6, -2.9, 0), a, exterior-1)

    a, b = ranges['door']
    camera('door', 'bishop_house', a, b, loc=(54.7, -12, 1.3), target=(57, -9.3, 1.35), lens=35)
    block('valjean', (57, -9.9, 0), a, b, 'knock', rot=math.pi)
    door = bpy.data.objects['bishop_street_door']
    key(door, 'rotation_euler', (0, 0, 0), a, True)
    key(door, 'rotation_euler', (0, 0, 0), cue('door', 'knocks'))
    key(door, 'rotation_euler', (0, 0, 1.25), b)
    half('valjean', (57, -9.9, 0), a, b)

    a, b = ranges['dinner']
    camera('dinner', 'dining_room', a, b, lens=35, end_loc=(58.8, -5.4, 1.35), end_target=(57, -3.8, 1.02))
    for name, pos, rot in [('bishop', (55.7, -3.8, 0), math.pi/2), ('valjean', (58.3, -3.8, 0), -math.pi/2)]:
        block(name, pos, a, b, 'sit_table_idle', rot=rot)
        half(name, pos, a, b)
    # Props' accepted relative layout is translated onto the actual world table.
    layout = ctx.prop_anchors['dining_room']
    for name in ('candlestick_1', 'candlestick_2', 'wicker_basket', 'rye_loaf', 'wine_bottle'):
        off = layout[name]
        prop(name, (57+off[0], -3.8+off[1], off[2]), a)
    for i, off in enumerate(layout['place_settings'], 1):
        for name, dx in [('bowl', 0), ('wine_glass', .16)]:
            prop('%s_%d' % (name, i), (57+off[0]+dx, -3.8+off[1], off[2]), a)
        # Cutlery leaves the basket for dinner; restore local basket placement later.
        for kind, dx in [('fork', -.14), ('spoon', .13)]:
            obj = ctx.props['%s_%d' % (kind, i)]
            world_pos = Vector((57+off[0]+dx, -3.8+off[1], off[2]+.02))
            bpy.context.view_layer.update()
            prop(obj.name, obj.parent.matrix_world.inverted() @ world_pos, a)
    lit = cue('dinner', 'lights')
    for name in ('candlestick_1', 'candlestick_2', 'iron_candlestick'):
        root = ctx.props[name]
        if name != 'iron_candlestick':
            resting = root.location.copy()
            key(root, 'location', resting + Vector((0, 0, .12)), a, True)
            key(root, 'location', resting, lit)
        flame, lamp = bpy.data.objects[root['flame_object']], bpy.data.objects[root['flame_light']]
        key(lamp.data, 'energy', 0, 1, True)
        key(flame, 'hide_render', True, 1, True)
        if name != 'iron_candlestick':
            key(lamp.data, 'energy', 1.2, lit, True)
            key(flame, 'hide_render', False, lit, True)
            key(lamp.data, 'energy', 0, b+1, True)
            key(flame, 'hide_render', True, b+1, True)

    a, b = ranges['night']
    wake = cue('night', 'wakes')
    camera('night_clock', 'cathedral', a, wake-1, loc=(8, 5, 26.8), target=(8, 17.6, 28), lens=65)
    camera('night_eyes', 'guest_alcove', wake, b, loc=(63, -5.8, 1.4), target=(64, -4.9, 1), lens=65)
    block('valjean', (64, -6.4, .05), a, wake-1, pose='sleep', rot=math.pi)
    block('valjean', (64, -6.4, .05), wake, b, 'idle_nervous', rot=math.pi)

    a, b = ranges['bedside']
    camera('bedside', 'bishop_bedroom', a, b, loc=(60.8, -2.5, 2.05),
           target=(63.1, -1.1, 1.1), end_loc=(61.2, -2.3, 1.95), lens=30)
    # Align the evaluated sleeping head to the actual modeled pillow, retaining
    # pi yaw so the body follows the bed's long Y axis (head to the north).
    sleeper = block('bishop', (63.7, -1.2, 0), a, b, pose='sleep', rot=math.pi)
    scene.frame_set(a)
    bpy.context.view_layer.update()
    rig = actors.ACTORS['bishop'].rig
    head_bone = actors._bone(rig, 'head')
    head_pos = rig.matrix_world @ rig.pose.bones[head_bone.name].head
    pillow = bpy.data.objects['bishop_bed_pillow']
    rest = sleeper.location + Vector((pillow.location.x-head_pos.x,
                                     pillow.location.y-head_pos.y,
                                     pillow.location.z+.12-head_pos.z))
    key(sleeper, 'location', rest, a, True)
    block('valjean', (62.1, -1.2, 0), a, b, pose='iron_candlestick_raised', rot=math.pi/2)
    prop('iron_candlestick', (62.5, -1.15, 1.65), a)
    # Narrow source just inside the real north window: no second face key.
    light('BEDSIDE_MOON', (63, .7, 2.2), (63.7, -.42, .9), a, b,
          180, (.4, .55, 1), .16)

    a, b = ranges['steal']
    jump = cue('steal', 'jumps')
    camera('steal_cupboard', 'bishop_bedroom', a, jump-1, target=(60.8, -.8, 1.15), lens=50)
    camera('steal_wall', 'garden', jump, b, loc=(55.5, 14, 2.8),
           target=(60, 19, 1.8), end_target=(60, 20, 1.2), lens=30)
    light('VAULT_MOON_RIM', (62, 22, 5), (60, 19, 1.8), jump, b,
          450, (.38, .53, 1), .6)
    block('valjean', (61.5, -.8, 0), a, jump-1, 'crouch_idle', rot=-math.pi/2)
    block('valjean', (60, 18, 0), jump, b, pose='vault', rot=math.pi)
    cupboard = bpy.data.objects['silver_cupboard_door']
    key(cupboard, 'rotation_euler', (0, 0, 0), a, True)
    key(cupboard, 'rotation_euler', (0, 0, -1.5), cue('steal', 'takes'))
    basket = prop('wicker_basket', (60.8, -.8, 1.15), ranges['night'][0])
    key(basket, 'location', (60.8, -.8, 1.15), cue('steal', 'takes'))
    key(basket, 'location', (61.5, -.8, 1.3), word_end('steal', 'silver'))
    key(basket, 'location', (60, 18, 1.2), jump, True)
    key(basket, 'location', (61.5, 16, 2.7), (jump+b)/2)
    key(basket, 'location', LOCATIONS['garden']['anchors']['basket_landing'], b)
    for kind in ('fork', 'spoon'):
        for i in range(1, 7):
            prop('%s_%d' % (kind, i), (-.025 if kind == 'fork' else .025, (i-3.5)*.011, .017+i*.004), ranges['night'][0])

    a, b = ranges['caught']
    camera('caught', 'bishop_house', a, b, loc=(53, -16, 2), target=(57, -13.2, 1.2),
           end_loc=(53, -13.5, 2), end_target=(57, -10.7, 1.2), lens=35)
    # Forward is -Y: pi yaw faces the doorway to the north (+Y).
    for name, dx, lead in [('valjean', 0, 0), ('gendarme_1', -.45, 0),
                           ('gendarme_2', .45, 0), ('gendarme_3', 0, .85)]:
        pos = (57+dx, -13.2+lead, 0)
        block(name, pos, a, b, 'walk', rot=math.pi,
              points=[pos, (57+dx, -10.7+lead, 0)],
              pose='held' if name == 'valjean' else None)
    rim = light('ESCORT_DAWN_BACKLIGHT', (58, -8.5, 4), (57, -12, 1.1),
                a, b, 500, (1, .75, .5), .25)
    for name in ('gendarme_1', 'gendarme_2', 'gendarme_3'):
        scene.frame_set(a)
        actors.face_light(name, rim)
    half('valjean', (57, -13.2, 0), a, b, (1, .75, .5))

    a, b = ranges['cliff']
    reveal = cue('cliff', 'bishop')
    camera('cliff_threshold', 'dining_room', a, reveal-1,
           loc=(58.1, -6.5, 1.7), target=(57, -10.5, 1.2), lens=32)
    # Reverse angle outside the opening, looking north at his south-facing face.
    camera('cliff_bishop', 'bishop_house', reveal, cut-1,
           loc=(58.4, -11.4, 1.65), target=(57, -8.55, 1.52),
           end_loc=(57.65, -9.65, 1.62), end_target=(57, -8.55, 1.58), lens=55)
    block('bishop', (57, -8.55, 0), a, cut-1, 'idle', rot=0)
    half('bishop', (57, -8.55, 0), a, cut-1, (1, .75, .5))
    for name, x, y in [('valjean', 57, -10.7), ('gendarme_1', 56.55, -10.7),
                       ('gendarme_2', 57.45, -10.7), ('gendarme_3', 57.8, -10)]:
        block(name, (x, y, 0), a, cut-1,
              pose='held' if name == 'valjean' else None, rot=math.pi)
    # The leading officer presents the basket at his near hand, below the bishop.
    prop('wicker_basket', (57.5, -9.8, 1.02), a)
    # Head tracking runs after the idle NLA, so the gaze survives clip evaluation.
    scene.frame_set(a)
    bishop = actors.ACTORS['bishop']
    head = actors._bone(bishop.rig, 'head')
    pb = bishop.rig.pose.bones[head.name]
    gaze = bpy.data.objects.new('BISHOP_GAZE', None)
    cams.objects.link(gaze)
    for frame, target in ((a, (57, -10.7, 1.55)),
                          (cue('cliff', 'looks'), (57.5, -9.8, 1.02)),
                          (cue('cliff', 'silver'), (57.5, -9.8, 1.02)),
                          (cue('cliff', 'Valjean'), (57, -10.7, 1.55)),
                          (cut-1, (57, -10.7, 1.55))):
        key(gaze, 'location', target, frame)
    constraint = pb.constraints.new('DAMPED_TRACK')
    constraint.name = 'Cliff_head_gaze'
    constraint.target = gaze
    # Determine the imported head's local forward axis from its world rest basis.
    basis = (bishop.rig.matrix_world @ head.matrix_local).to_quaternion()
    axes = {'TRACK_X': (1, 0, 0), 'TRACK_NEGATIVE_X': (-1, 0, 0),
            'TRACK_Y': (0, 1, 0), 'TRACK_NEGATIVE_Y': (0, -1, 0),
            'TRACK_Z': (0, 0, 1), 'TRACK_NEGATIVE_Z': (0, 0, -1)}
    constraint.track_axis = max(axes, key=lambda axis: (basis @ Vector(axes[axis])).dot(Vector((0, -1, 0))))
    for frame, value in ((1, 0), (a, 1), (cut, 0)):
        key(constraint, 'influence', value, frame, True)
    key(door, 'rotation_euler', (0, 0, 0), a, True)
    key(door, 'rotation_euler', (0, 0, 0), cue('cliff', 'opens'))
    key(door, 'rotation_euler', (0, 0, 1.25), word_end('cliff', 'opens'))

    # Location collections remain coherent; flashbacks are isolated. Bake their
    # switches to renderable objects because collection flags cannot be keyed.
    for name in LOCATIONS:
        col = ctx.col(name)
        for obj in walk(col):
            if name.endswith('_flashback'):
                sid = 'bread' if name.startswith('bakery') else 'years'
                # Preserve the timed broken-pane visibility above.
                if not obj.get('breakable'):
                    visible(obj, *ranges[sid])
            else:
                for sid in SHOT_IDS:
                    key(obj, 'hide_render', sid in ('bread', 'years'), ranges[sid][0], True)
                key(obj, 'hide_render', True, cut, True)
    actor_shots = {'valjean': [s for s in SHOT_IDS if s != 'bishop'],
                  'bishop': ['bishop', 'dinner', 'bedside', 'cliff']}
    for name in ('valjean', 'bishop', 'gendarme_1', 'gendarme_2', 'gendarme_3'):
        allowed = actor_shots.get(name, ['caught', 'cliff'])
        for obj in walk(ctx.col('ACTOR_' + name)):
            key(obj, 'hide_render', True, 1, True)
            for sid in allowed:
                a, b = ranges[sid]
                key(obj, 'hide_render', False, a, True)
                key(obj, 'hide_render', True, min(b+1, cut), True)
    # Hide unused prop roots, revealing only their scheduled scenes.
    usage = {'yellow_passport': ['passport'], 'bakery_loaf': ['bread'],
             'iron_chain': ['years'], 'iron_candlestick': ['bedside'],
             'wicker_basket': ['dinner', 'steal', 'cliff']}
    for name, root in ctx.props.items():
        if root.parent:  # basket cutlery follows basket visibility below
            continue
        allowed = usage.get(name, ['dinner'])
        for obj in tree(root):
            if 'flame' in obj.name:
                continue
            key(obj, 'hide_render', True, 1, True)
            for sid in allowed:
                a, b = ranges[sid]
                key(obj, 'hide_render', False, a, True)
                key(obj, 'hide_render', True, min(b+1, cut), True)
    # Absolute black via compositor at the END of says, irrespective of HDRI,
    # exposure, geometry, motion blur, or random-access chunk boundaries.
    scene.use_nodes = True
    nt = scene.node_tree
    nt.nodes.clear()
    render = nt.nodes.new('CompositorNodeRLayers')
    mix = nt.nodes.new('CompositorNodeMixRGB')
    mix.blend_type = 'MIX'
    mix.inputs[2].default_value = (0, 0, 0, 1)
    grade = nt.nodes.new('CompositorNodeHueSat')
    nt.links.new(render.outputs['Image'], grade.inputs['Image'])
    for sid in SHOT_IDS:
        key(grade.inputs['Saturation'], 'default_value', .22 if sid in ('bread', 'years') else 1, ranges[sid][0], True)
    nt.links.new(grade.outputs['Image'], mix.inputs[1])
    out = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(mix.outputs[0], out.inputs[0])
    key(mix.inputs[0], 'default_value', 0, 1, True)
    key(mix.inputs[0], 'default_value', 1, cut, True)
    scene['black_cut_frame'] = cut
    scene['preview_frames'] = str(PREVIEW_FRAMES)
    scene.frame_set(1)
    print('[shots] built 13 shots; black cut at frame %d; end card owned by post' % cut)
