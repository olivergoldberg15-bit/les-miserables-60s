"""Rocketbox cast and period wardrobe for Blender 4.2.

Shots use ACTORS[name] (also ctx.cast[name]), place(), play(), pose(),
move_along(), and face_light().
Coordinates: metres, Z up, character forward -Y; rotations are XYZ radians.
Animation is in-place: shots animate the actor root for travel. Loop strips run
until scene.frame_end; shots must trim strip.frame_end when blocking changes.
No fallback humans or invented motion: missing assets/bones fail explicitly.
"""
import math
from pathlib import Path
import re
from types import SimpleNamespace

import bpy
from mathutils import Vector
from lib import look_at

AVATARS = {name: name for name in
           ('valjean', 'bishop', 'gendarme_1', 'gendarme_2', 'gendarme_3')}
CLIPS = ('walk', 'walk_weary', 'idle', 'idle_nervous', 'look_around',
         'knock', 'try_door', 'sit_down_table', 'sit_table_idle',
         'sit_chair_idle', 'crouch_in', 'crouch_idle', 'talk', 'angry')
CLIP_ALIASES = {'eat': 'sit_table_idle', 'sit': 'sit_down_table',
                'struggle': 'walk_weary', 'hand_raise': 'knock',
                'crouch': 'crouch_in'}
ACTORS = {}
_CTX = None
_ACTIONS = {}


def _bone_key(name):
    return re.sub('[^a-z0-9]', '', name.rsplit(':', 1)[-1].lower())


def _bone(rig, *terms):
    terms = tuple(variant for term in terms for variant in
                  (term, term.replace('left', 'l').replace('right', 'r')))
    terms = tuple(_bone_key(t) for t in terms)
    for term in terms:
        matches = [b for b in rig.data.bones if _bone_key(b.name).endswith(term)]
        if len(matches) == 1:
            return matches[0]
    raise RuntimeError(f'[actors] {rig.name}: required bone {terms} missing/ambiguous')


def _import(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True,
                             automatic_bone_orientation=False, use_image_search=True)
    objects = set(bpy.data.objects) - before
    rigs = [o for o in objects if o.type == 'ARMATURE']
    if len(rigs) != 1:
        raise RuntimeError(f'[actors] {path}: expected one armature, got {len(rigs)}')
    return rigs[0], objects


def _move(obj, collection):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    collection.objects.link(obj)


def _textures(objects, directory):
    """Repair imported maps without making an absent texture fatal."""
    files = {p.name.lower(): p for p in Path(directory).rglob('*') if p.is_file()}
    for obj in objects:
        if obj.type != 'MESH':
            continue
        for material in obj.data.materials:
            if not material or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type != 'TEX_IMAGE' or not node.image:
                    continue
                name = node.image.filepath.replace('\\', '/').rsplit('/', 1)[-1].lower()
                path = files.get(name)
                if path:
                    try:
                        node.image.filepath = str(path)
                        node.image.reload()
                    except Exception as exc:
                        print(f'[actors] WARNING texture {name}: {exc}', flush=True)
                elif not node.image.packed_file:
                    print(f'[actors] WARNING missing avatar texture: {name}', flush=True)
    return files


def _point(actor, bone, tail=False):
    return actor.rig.matrix_local @ (bone.tail_local if tail else bone.head_local)


def _material(name, color, roughness=.85, metallic=0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return material


def _region_mask(obj):
    """Rocketbox packs clothes and hands into one body texture, so garment regions
    come from dominant skin weights: R = bare skin, G = legs, B = feet."""
    names = {g.index: _bone_key(g.name) for g in obj.vertex_groups}
    attrs = obj.data.color_attributes
    attr = attrs.get('period_region') or attrs.new('period_region', 'FLOAT_COLOR', 'POINT')
    for v in obj.data.vertices:
        key = names.get(max(v.groups, key=lambda g: g.weight).group, '') if v.groups else ''
        feet = any(t in key for t in ('foot', 'toe'))
        legs = not feet and any(t in key for t in ('thigh', 'calf', 'leg'))
        skin = any(t in key for t in ('head', 'neck', 'hand', 'finger', 'thumb'))
        attr.data[v.index].color = (float(skin), float(legs), float(feet), 1.0)


def _wardrobe(actor, files):
    """Material-only treatment: never cut or replace the Rocketbox human."""
    copies = {}
    for obj in actor.imported:
        if obj.type != 'MESH':
            continue
        _region_mask(obj)
        for slot in obj.material_slots:
            original = slot.material
            if original is None:
                continue
            if original in copies:
                slot.material = copies[original]
                continue
            material = original.copy()
            copies[original] = material
            slot.material = material
            material.use_nodes = True
            nodes, links = material.node_tree.nodes, material.node_tree.links
            shader = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if shader is None:
                print(f'[actors] WARNING no Principled shader: {material.name}', flush=True)
                continue
            images = [n for n in nodes if n.type == 'TEX_IMAGE' and n.image]
            identity = ' '.join([original.name] + [n.image.name + ' ' + n.image.filepath for n in images]).lower()
            diffuse = next((n for n in images if any(t in (n.image.name + n.image.filepath).lower()
                            for t in ('diffuse', 'albedo', 'basecolor', 'base_color'))), None)
            incoming = next(iter(shader.inputs['Base Color'].links), None)
            if diffuse is None and incoming and incoming.from_node.type == 'TEX_IMAGE':
                diffuse = incoming.from_node
            if diffuse and not incoming:
                links.new(diffuse.outputs['Color'], shader.inputs['Base Color'])
                incoming = next(iter(shader.inputs['Base Color'].links), None)
            # Cards must cast their cutout silhouette, never an opaque eye band.
            if any(t in identity for t in ('lash', 'brow', 'hair', 'opacity')):
                opacity = next((n for n in images if 'opacity' in (n.image.name + n.image.filepath).lower()), None)
                if opacity is None and diffuse:
                    stem = re.sub(r'(?i)(diffuse|albedo|basecolor|base_color).*', '', Path(diffuse.image.name).stem)
                    path = next((p for name, p in sorted(files.items())
                                 if stem and name.startswith(stem.lower()) and 'opacity' in name), None)
                    if path:
                        try:
                            opacity = nodes.new('ShaderNodeTexImage')
                            opacity.image = bpy.data.images.load(str(path), check_existing=True)
                            opacity.image.colorspace_settings.name = 'Non-Color'
                            for uv_link in diffuse.inputs['Vector'].links:
                                links.new(uv_link.from_socket, opacity.inputs['Vector'])
                        except Exception as exc:
                            print(f'[actors] WARNING opacity {path}: {exc}', flush=True)
                            opacity = None
                # Rocketbox *_opacity_color.tga is 32-bit: the cutout lives in its alpha channel.
                cutout = opacity or diffuse
                if cutout:
                    cutout.image.alpha_mode = 'STRAIGHT'
                    links.new(cutout.outputs['Alpha'], shader.inputs['Alpha'])
                # Blender 4.2 replaces the legacy HASHED enum with DITHERED.
                if hasattr(material, 'surface_render_method'):
                    material.surface_render_method = 'DITHERED'
                elif hasattr(material, 'blend_method'):
                    material.blend_method = 'HASHED'
                if hasattr(material, 'shadow_method'):
                    material.shadow_method = 'HASHED'
            if any(t in identity for t in ('eye', 'cornea')):
                shader.inputs['Roughness'].default_value = .08 if 'cornea' in identity else .25
                if 'cornea' in identity:
                    transmission = shader.inputs.get('Transmission Weight') or shader.inputs.get('Transmission')
                    if transmission:
                        transmission.default_value = 1
                    shader.inputs['IOR'].default_value = 1.376
                    if not diffuse:
                        shader.inputs['Base Color'].default_value = (1, 1, 1, 1)
            if any(t in identity for t in ('head', 'eye', 'cornea', 'hair', 'lash', 'brow', 'teeth', 'tooth', 'opacity')):
                continue
            coat = ((.17, .105, .055) if actor.name == 'valjean' else
                    (.012, .013, .017) if actor.name == 'bishop' else (.018, .035, .085))
            legs = (coat if actor.name == 'bishop' else
                    (.035, .029, .024) if actor.name == 'valjean' else (.75, .72, .65))
            shoes = (.025, .018, .014)
            # Original luminance preserves modeled/painted folds and seams;
            # imported normal/bump connections remain completely untouched.
            region = nodes.new('ShaderNodeAttribute')
            region.attribute_type = 'GEOMETRY'
            region.attribute_name = 'period_region'
            split = nodes.new('ShaderNodeSeparateColor')
            links.new(region.outputs['Color'], split.inputs[0])
            def mix(fac, a, b, blend='MIX'):
                node = nodes.new('ShaderNodeMixRGB')
                node.blend_type = blend
                for socket, value in ((node.inputs[0], fac), (node.inputs[1], a), (node.inputs[2], b)):
                    if isinstance(value, tuple):
                        socket.default_value = (*value, 1) if len(value) == 3 else value
                    elif isinstance(value, (int, float)):
                        socket.default_value = value
                    else:
                        links.new(value, socket)
                return node.outputs[0]
            garment = mix(split.outputs['Blue'], mix(split.outputs['Green'], coat, legs), shoes)
            if incoming:
                luminance = nodes.new('ShaderNodeRGBToBW')
                links.new(incoming.from_socket, luminance.inputs[0])
                # Flatten modern prints (argyle, logos) but keep folds from the normal map.
                flat = mix(.7, luminance.outputs[0], (.42, .42, .42))
                tinted = mix(1.0, flat, garment, 'MULTIPLY')
                # Bare skin (face, neck, hands) keeps the original texture.
                links.new(mix(split.outputs['Red'], tinted, incoming.from_socket), shader.inputs['Base Color'])
            else:
                base = shader.inputs['Base Color'].default_value
                value = .2126*base[0] + .7152*base[1] + .0722*base[2]
                links.new(mix(1.0, (value, value, value), garment, 'MULTIPLY'), shader.inputs['Base Color'])
            for link in list(shader.inputs['Roughness'].links):
                links.remove(link)
            shader.inputs['Roughness'].default_value = .85


def _accessory(actor, name, vertices, faces, material, bone):
    mesh = bpy.data.meshes.new(actor.name + '_' + name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(mesh.name, mesh)
    actor.collection.objects.link(obj)
    obj.parent = actor.root
    obj.data.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    group = obj.vertex_groups.new(name=bone.name)
    group.add(list(range(len(vertices))), 1, 'REPLACE')
    actor.costume.append(obj)
    return obj


def _extras(actor):
    if actor.name != 'valjean':
        return
    chest = _bone(actor.rig, 'spine2', 'spine1', 'spine')
    center = _point(actor, chest) + Vector((0, .25, -.12))
    corners = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
               (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]
    bag = _accessory(actor, 'soft_knapsack',
        [tuple(center + Vector((x*.19,y*.09,z*.24))) for x,y,z in corners],
        [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],
        _material('Valjean_canvas', (.095,.065,.035)), chest)
    # A rounded box reads as a canvas pack; plain subdivision of a cube reads as an egg.
    bevel = bag.modifiers.new('Soft canvas edges', 'BEVEL')
    bevel.width, bevel.segments, bevel.limit_method = .045, 4, 'NONE'
    sub = bag.modifiers.new('Canvas sag', 'SUBSURF')
    sub.levels = sub.render_levels = 1
    displacement = bag.modifiers.new('Canvas irregularity', 'DISPLACE')
    noise = bpy.data.textures.new('Knapsack deterministic clouds', type='CLOUDS')
    noise.noise_scale = .09
    displacement.texture = noise
    displacement.strength = .01
    displacement.texture_coords = 'LOCAL'
    deform = bag.modifiers.new('Rocketbox attachment', 'ARMATURE')
    deform.object = actor.rig
    hand = _bone(actor.rig, 'righthand')
    hp = _point(actor, hand)
    for name, bottom, top, radius, material in (
        ('walking_stick', -.85, .25, .022, _material('Stick wood', (.045,.025,.015), .7)),
        ('iron_ferrule', -.88, -.77, .026, _material('Stick iron', (.12,.13,.14), .55, .85))):
        count = 24
        vertices = [tuple(hp + Vector((radius*math.cos(i*math.tau/count),
                    radius*math.sin(i*math.tau/count), z)))
                    for z in (bottom, top) for i in range(count)]
        faces = [(i,(i+1)%count,count+(i+1)%count,count+i) for i in range(count)]
        faces += [tuple(reversed(range(count))), tuple(range(count,2*count))]
        stick = _accessory(actor, name, vertices, faces, material, hand)
        # Bone parent keeps the rigid prop attached through every hand pose.
        bpy.context.view_layer.update()
        world = stick.matrix_world.copy()
        stick.parent = actor.rig
        stick.parent_type = 'BONE'
        stick.parent_bone = hand.name
        bpy.context.view_layer.update()
        stick.matrix_world = world


def _resolve(actor):
    return ACTORS[actor.lower()] if isinstance(actor, str) else actor


def place(actor, loc, rot=(0, 0, 0)):
    """Return the placement root; caller may key its location/rotation."""
    actor = _resolve(actor)
    actor.root.location = loc
    actor.root.rotation_euler = (0, 0, rot) if isinstance(rot, (float, int)) else rot
    return actor.root


def _load_action(actor, clip):
    path = _CTX.assets.rocketbox_anim(clip)
    if not Path(path).stem.lower().startswith('m_'):
        raise RuntimeError(f'[actors] male Rocketbox m_* clip required: {path}')
    source, objects = _import(path)
    try:
        action = source.animation_data.action if source.animation_data else None
        if action is None:
            raise RuntimeError(f'[actors] no animation action in {path}')
        from mathutils import Euler, Quaternion
        # World-orientation retarget. Rocketbox clip files bind in the clip's own
        # stance while avatars bind in T-pose, so copying rest-relative deltas leaves
        # avatars in T-pose. Instead rebuild each source bone's posed orientation per
        # frame from its curves, and solve the target basis that gives the target
        # bone the same world orientation (both files share the Max biped node axes).
        target = {_bone_key(b.name): b for b in actor.rig.data.bones}
        mapping = {}
        for bone in source.data.bones:
            key = _bone_key(bone.name)
            if key in target:
                mapping[bone.name] = target[key].name
            elif not ('nub' in key or 'footsteps' in key):
                raise RuntimeError(f'[actors] incompatible clip bone {bone.name}: {clip}')
        curves = {}
        for curve in action.fcurves:
            match = re.match(r'pose\.bones\["(.+?)"\]\.(rotation_quaternion|rotation_euler|location)$', curve.data_path)
            if match:
                curves.setdefault(match.group(1), {}).setdefault(match.group(2), {})[curve.array_index] = curve
        def ordered(bones):
            depth = lambda b: 0 if b.parent is None else 1 + depth(b.parent)
            return sorted(bones, key=depth)
        src_bones, tgt_bones = ordered(source.data.bones), ordered(actor.rig.data.bones)
        rest_s = {b.name: b.matrix_local.to_quaternion() for b in src_bones}
        rest_t = {b.name: b.matrix_local.to_quaternion() for b in tgt_bones}
        obj_s = source.matrix_world.to_quaternion()
        obj_t = actor.rig.matrix_world.to_quaternion()
        back = {v: k for k, v in mapping.items()}
        root_t = tgt_bones[0].name
        scale_s = source.matrix_world.to_scale()[0]
        scale_t = actor.rig.matrix_world.to_scale()[0]
        def basis_s(name, frame):
            chans = curves.get(name, {})
            if 'rotation_quaternion' in chans:
                c = chans['rotation_quaternion']
                return Quaternion([c[i].evaluate(frame) if i in c else (1 if i == 0 else 0) for i in range(4)]).normalized()
            if 'rotation_euler' in chans:
                c = chans['rotation_euler']
                mode = source.pose.bones[name].rotation_mode
                return Euler([c[i].evaluate(frame) if i in c else 0 for i in range(3)],
                             mode if len(mode) == 3 else 'XYZ').to_quaternion()
            return Quaternion()
        first, last = (int(v) for v in action.frame_range)
        frames = list(range(first, last + 1))
        # Clips bake their own root yaw; turn the whole clip about world Z so its
        # first-frame root faces the way the avatar's rest root faces. Shots aim actors.
        src_root = back[root_t]
        start = obj_s @ rest_s[src_root] @ basis_s(src_root, first)
        rest_root = obj_t @ rest_t[root_t]
        axis = min((Vector(a) for a in ((1, 0, 0), (0, 1, 0), (0, 0, 1))), key=lambda a: abs((rest_root @ a).z))
        want, have = rest_root @ axis, start @ axis
        yaw = Quaternion((0, 0, 1), math.atan2(want.y, want.x) - math.atan2(have.y, have.x))
        keys = {b.name: [] for b in tgt_bones if b.name in back}
        bob = []
        for frame in frames:
            pose_s = {}
            for b in src_bones:
                local = basis_s(b.name, frame)
                if b.parent is None:
                    pose_s[b.name] = rest_s[b.name] @ local
                else:
                    pose_s[b.name] = pose_s[b.parent.name] @ rest_s[b.parent.name].inverted() @ rest_s[b.name] @ local
            pose_t = {}
            for b in tgt_bones:
                rel = rest_t[b.name] if b.parent is None else (
                    pose_t[b.parent.name] @ rest_t[b.parent.name].inverted() @ rest_t[b.name])
                if b.name in back:
                    pose_t[b.name] = obj_t.inverted() @ yaw @ obj_s @ pose_s[back[b.name]]
                    q = rel.inverted() @ pose_t[b.name]
                    q.normalize()
                    if keys[b.name] and keys[b.name][-1].dot(q) < 0:
                        q.negate()  # continuous hemisphere for clean interpolation
                    keys[b.name].append(q)
                else:
                    pose_t[b.name] = rel
            # In-place vertical bob of the root in world space, scaled to the target.
            loc = curves.get(src_root, {}).get('location', {})
            v = Vector([loc[i].evaluate(frame) if i in loc else 0 for i in range(3)])
            world = obj_s @ rest_s[src_root] @ v * scale_s if src_root else Vector()
            bob.append((rest_t[root_t].inverted() @ obj_t.inverted() @ Vector((0, 0, world.z))) / scale_t)
        result = bpy.data.actions.new(f'AN_{actor.name}_{clip}')
        def write(bone_name, path, values):
            data_path = f'pose.bones["{bone_name}"].{path}'
            for index in range(len(values[0])):
                curve = result.fcurves.new(data_path, index=index, action_group=bone_name)
                curve.keyframe_points.add(len(frames))
                for point, frame, value in zip(curve.keyframe_points, frames, values):
                    point.co = (frame, value[index])
                    point.interpolation = 'LINEAR'
                curve.update()
        for bone_name, values in keys.items():
            write(bone_name, 'rotation_quaternion', values)
        write(root_t, 'location', bob)
        for pose_bone in actor.rig.pose.bones:
            pose_bone.rotation_mode = 'QUATERNION'
        result.use_fake_user = True
        return result
    finally:
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)


def play(actor, clip, start_frame, speed=1.0, loop=False):
    """Schedule a shared-skeleton action in NLA, returning its editable strip.

    Each invocation owns a track. Later strips replace earlier ones; extrapolation
    is NOTHING to avoid a held pose overriding subsequent shot performances.
    """
    actor = _resolve(actor)
    clip = CLIP_ALIASES.get(clip, clip)
    if clip not in CLIPS or speed <= 0 or not math.isfinite(speed):
        raise ValueError(f'[actors] invalid clip/speed: {clip}/{speed}')
    key = actor.name, clip
    if key not in _ACTIONS:
        _ACTIONS[key] = _load_action(actor, clip)
    action = _ACTIONS[key]
    actor.rig.animation_data_create()
    actor.rig.animation_data.action = None
    track = actor.rig.animation_data.nla_tracks.new()
    track.name = f'{clip}_{start_frame}'
    strip = track.strips.new(action.name, int(start_frame), action)
    strip.frame_start = float(start_frame)
    strip.scale = 1 / speed
    # Hold the last pose until a later clip takes over, so gaps never snap to T-pose.
    # The actor's first clip also holds backwards to cover the frames before it.
    clips = [t for t in actor.rig.animation_data.nla_tracks if not t.name.startswith('authored_')]
    strip.extrapolation = 'HOLD' if len(clips) == 1 else 'HOLD_FORWARD'
    strip.blend_type = 'REPLACE'
    if loop:
        duration = max(1, action.frame_range[1]-action.frame_range[0]) / speed
        strip.repeat = max(1, (bpy.context.scene.frame_end-start_frame+1)/duration)
    return strip


def move_along(actor, points, frame_start, frame_end):
    """Key the placement root in metres; clips themselves remain in-place.

    Points are equally spaced in time. AUTO_CLAMPED handles ease endpoints;
    shots should supply more points for corners and trim overlapping moves.
    """
    actor = _resolve(actor)
    points = [Vector(p) for p in points]
    if len(points) < 2 or frame_end <= frame_start:
        raise ValueError('[actors] travel needs >=2 points and a positive range')
    for i, point in enumerate(points):
        frame = frame_start + (frame_end-frame_start)*i/(len(points)-1)
        actor.root.location = point
        actor.root.keyframe_insert(data_path='location', frame=frame)
    action = actor.root.animation_data.action
    for curve in action.fcurves:
        if curve.data_path == 'location':
            for key in curve.keyframe_points:
                key.interpolation = 'BEZIER'
                key.handle_left_type = key.handle_right_type = 'AUTO_CLAMPED'
    return actor.root


def pose(actor, name, frame_start, frame_end):
    """Hand-authored performances on the imported biped, in an NLA strip.

    Sleep lies along actor-local -Y, head toward -Y, face toward +Z;
    placement root is the feet anchor. Vault starts at a wall's near face,
    travels toward -Y over its 2.2m top and lands beyond it. These are blocking
    poses requiring cloud silhouette/contact review, not motion-capture clips.
    No pose changes the placement root; move_along can independently travel it.
    """
    from mathutils import Quaternion
    actor = _resolve(actor)
    if name == 'lie':
        name = 'sleep'
    if name not in ('sleep', 'vault', 'held', 'kneel', 'iron_candlestick_raised'):
        raise ValueError(f'[actors] unknown authored pose: {name}')
    if frame_end <= frame_start:
        raise ValueError('[actors] pose needs a positive frame range')
    rig = actor.rig
    rig.animation_data_create()
    previous = rig.animation_data.action
    action = bpy.data.actions.new(f'AN_{actor.name}_{name}_{frame_start}')
    rig.animation_data.action = action
    bones = {
        'hips': _bone(rig, 'hips', 'pelvis', 'bip01'),
        'chest': _bone(rig, 'spine2', 'spine1', 'spine'),
        'head': _bone(rig, 'head'),
    }
    for side in ('left', 'right'):
        for part, aliases in (('arm', ('arm', 'upperarm')),
                              ('forearm', ('forearm', 'lowerarm')),
                              ('thigh', ('upleg', 'thigh')),
                              ('shin', ('leg', 'calf'))):
            bones[side+part] = _bone(rig, *(side+t for t in aliases))
    saved = {b.name: b.matrix_basis.copy() for b in rig.pose.bones}
    # Angles below are actor-space rotation deltas from the imported rest pose.
    def sample(phase):
        angles = {'leftarm': (0, -1.25, 0), 'rightarm': (0, 1.25, 0)}
        offset = Vector((0, 0, 0))
        if name == 'sleep':
            angles.update(hips=(math.pi/2, 0, 0),
                          leftarm=(0, -1.05, -.35), rightarm=(0, 1.05, .35),
                          leftforearm=(-1.35, 0, 0), rightforearm=(-1.35, 0, 0))
            # Lower the pelvis from standing height (~1 m) onto a mattress top (~.75 m).
            offset.z = -.22
        elif name == 'held':
            angles.update(chest=(.28, 0, 0), head=(.25, 0, 0),
                          leftarm=(-.5, -1.1, 0), rightarm=(-.5, 1.1, 0),
                          leftforearm=(-.7, 0, 0), rightforearm=(-.7, 0, 0))
        elif name == 'kneel':
            angles.update(leftthigh=(-1.25, 0, 0), rightthigh=(-1.25, 0, 0),
                          leftshin=(1.65, 0, 0), rightshin=(1.65, 0, 0))
            offset.z = -.65
        elif name == 'iron_candlestick_raised':
            angles.update(rightarm=(0, -.55, -.9), rightforearm=(-1.4, 0, 0))
        else:
            lift = math.sin(math.pi*phase)
            angles.update(chest=(.65*lift, 0, 0),
                          rightarm=(-.9*lift, .3, -.7*lift),
                          leftthigh=(-1.5*lift, 0, 0),
                          rightthigh=(-1.15*lift, 0, 0),
                          leftshin=(1.6*lift, 0, 0), rightshin=(1.4*lift, 0, 0))
            offset = Vector((0, -2.0*phase, 1.65*lift))
        return angles, offset
    try:
        for phase in ((0, .2, .45, .65, .85, 1) if name == 'vault' else (0, 1)):
            frame = frame_start + phase*(frame_end-frame_start)
            for b in rig.pose.bones:
                b.matrix_basis.identity()
            angles, offset = sample(phase)
            for key, bone in bones.items():
                pb = rig.pose.bones[bone.name]
                basis = (rig.matrix_local.to_3x3() @ bone.matrix_local.to_3x3()).to_quaternion()
                q = Quaternion((1, 0, 0), 0)
                for axis, angle in zip(((1,0,0), (0,1,0), (0,0,1)), angles.get(key, (0,0,0))):
                    q = q @ Quaternion(axis, angle)
                pb.rotation_mode = 'QUATERNION'
                pb.rotation_quaternion = basis.inverted() @ q @ basis
                pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)
                if key == 'hips':
                    transform = rig.matrix_local.to_3x3() @ bone.matrix_local.to_3x3()
                    pb.location = transform.inverted() @ offset
                    pb.keyframe_insert(data_path='location', frame=frame)
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = 'BEZIER'
                point.handle_left_type = point.handle_right_type = 'AUTO_CLAMPED'
    finally:
        rig.animation_data.action = previous
        for b in rig.pose.bones:
            b.matrix_basis = saved[b.name]
    track = rig.animation_data.nla_tracks.new()
    track.name = f'authored_{name}_{frame_start}'
    strip = track.strips.new(action.name, int(frame_start), action)
    strip.frame_start = float(frame_start)
    strip.extrapolation = 'NOTHING'
    strip.blend_type = 'REPLACE'
    return strip


def face_light(actor, key_light):
    """Aim motivated key from the actor's side; flag faces with negative fill.

    Call after blocking. Returns a head-following opaque flag. This is physical
    light control, not a shader trick; cloud lookdev must check every camera.
    Extras' flag sits toward the key, principals' flag on the opposite cheek.
    Do not share a movable key across actors; use one motivated light per face.
    """
    actor = _resolve(actor)
    head = _bone(actor.rig, 'head')
    bpy.context.view_layer.update()
    point = actor.rig.matrix_world @ actor.rig.pose.bones[head.name].head
    extra = actor.name.startswith('gendarme')
    if not extra:
        distance = max(1, (key_light.location-point).length)
        side = actor.root.matrix_world.to_quaternion() @ Vector((1, -.15, .25))
        key_light.location = point + side.normalized()*distance
        look_at(key_light, point)
    flag = actor.flag
    toward = (key_light.location-point).normalized()
    flag.location = point + toward*(.24 if extra else -.22)
    flag.rotation_euler = toward.to_track_quat('Z','Y').to_euler()
    flag.hide_render = False
    # Follow animated head without changing the just-computed world placement.
    world = flag.matrix_world.copy()
    flag.parent = actor.rig
    flag.parent_type = 'BONE'
    flag.parent_bone = head.name
    bpy.context.view_layer.update()
    flag.matrix_world = world
    return flag


def build(ctx):
    global _CTX
    _CTX = ctx
    if ACTORS:
        raise RuntimeError('[actors] build requires a fresh scene/module state')
    for name, avatar in AVATARS.items():
        asset = ctx.assets.rocketbox(avatar)
        rig, objects = _import(asset['fbx'])
        collection = ctx.col('ACTOR_' + name)
        root = bpy.data.objects.new(name, None)
        collection.objects.link(root)
        # Link actor collections under ACTORS, not twice under the scene root.
        parent = ctx.col('ACTORS')
        if collection.name not in parent.children:
            parent.children.link(collection)
        if collection.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(collection)
        for obj in objects:
            _move(obj, collection)
            if obj.parent not in objects:
                obj.parent = root
        rig.name = name + '_rig'
        rig.animation_data_clear()
        from mathutils import Matrix
        for pose_bone in rig.pose.bones:
            pose_bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        meshes = [o for o in objects if o.type == 'MESH']
        points = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
        if not points:
            raise RuntimeError(f'[actors] {avatar} has no mesh')
        height = max(p.z for p in points)-min(p.z for p in points)
        if height <= 0:
            raise RuntimeError(f'[actors] invalid avatar height: {avatar}')
        factor = (1.81 if name == 'valjean' else 1.73)/height
        # Apply uniform unit conversion on top-level imported objects, retaining
        # original mesh/armature bind transforms and the shared bone basis.
        for obj in objects:
            if obj.parent == root:
                obj.scale *= factor
                obj.location *= factor
        bpy.context.view_layer.update()
        actor = SimpleNamespace(name=name, root=root, rig=rig, collection=collection,
                                imported=objects, costume=[], flag=None)
        files = _textures(objects, asset['textures'])
        _wardrobe(actor, files)
        _extras(actor)
        # Flag hidden until a shot supplies its motivated key light.
        black = _material(name+'_negative_fill', (.002,.002,.002))
        flag = _accessory(actor, 'face_flag',
                          [(-.21,-.24,0),(.21,-.24,0),(.21,.24,0),(-.21,.24,0)],
                          [(0,1,2,3)], black, _bone(rig,'head'))
        flag.vertex_groups.clear()
        flag.visible_camera = False
        flag.visible_glossy = False
        flag.hide_render = True
        actor.flag = flag
        ACTORS[name] = actor
        print(f'[actors] imported {name}: {avatar}; period wardrobe fitted', flush=True)
    ctx.cast = ACTORS
    return ACTORS
