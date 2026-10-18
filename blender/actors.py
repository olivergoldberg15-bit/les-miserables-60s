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
from lib import pbr_material, look_at

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
    """Relink FBX image basenames against the separately downloaded textures."""
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
                    node.image.filepath = str(path)
                    node.image.reload()
                elif not node.image.packed_file:
                    raise RuntimeError(f'[actors] missing avatar texture: {name} in {directory}')


def _cloth(ctx, name, color, key='cloth_wool', roughness=.92, metallic=0):
    mat = pbr_material(ctx, key, scale=7, name='ACTOR_' + name)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    incoming = next(iter(shader.inputs['Base Color'].links), None)
    if incoming:
        tint = nodes.new('ShaderNodeMixRGB')
        tint.blend_type = 'MULTIPLY'
        tint.inputs[0].default_value = 1
        tint.inputs[2].default_value = (*color, 1)
        links.new(incoming.from_socket, tint.inputs[1])
        links.new(tint.outputs[0], shader.inputs['Base Color'])
    for link in list(shader.inputs['Roughness'].links):
        links.remove(link)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return mat


def _mesh(actor, name, verts, faces, mat, weights):
    mesh = bpy.data.meshes.new(actor.name + '_' + name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(mesh.name, mesh)
    actor.collection.objects.link(obj)
    obj.parent = actor.root
    obj.data.materials.append(mat)
    # Bone coordinates are transformed into actor metres, so deform modifier
    # uses the same world-space bind transform as the imported skeleton.
    groups = {}
    for i, influences in enumerate(weights):
        total = sum(influences.values())
        for bone, weight in influences.items():
            if bone not in groups:
                groups[bone] = obj.vertex_groups.new(name=bone)
            groups[bone].add([i], weight / total, 'REPLACE')
    mod = obj.modifiers.new('Rocketbox wardrobe deformation', 'ARMATURE')
    mod.object = actor.rig
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    actor.costume.append(obj)
    return obj


def _ring(actor, name, levels, mat, bone, segments=48):
    """Elliptical tailored shell; radii and centres are in actor-local metres."""
    verts = [(x + rx * math.cos(2 * math.pi * i / segments),
              y + ry * math.sin(2 * math.pi * i / segments), z)
             for x, y, z, rx, ry in levels for i in range(segments)]
    faces = [(j * segments + i, j * segments + (i+1) % segments,
              (j+1) * segments + (i+1) % segments, (j+1) * segments + i)
             for j in range(len(levels)-1) for i in range(segments)]
    obj = _mesh(actor, name, verts, faces, mat, [{bone.name: 1}] * len(verts))
    solid = obj.modifiers.new('Wool thickness', 'SOLIDIFY')
    solid.thickness = .006
    return obj


def _tube(actor, name, start, end, radius, mat, bone, end_radius=None):
    start, end = Vector(start), Vector(end)
    direction = (end-start).normalized()
    side = direction.cross(Vector((0, 1, 0)))
    if side.length < .01:
        side = direction.cross(Vector((1, 0, 0)))
    side.normalize()
    other = direction.cross(side).normalized()
    verts = []
    for point, r in ((start, radius), (end, end_radius or radius)):
        verts.extend(tuple(point + r * (side * math.cos(i*math.tau/20) +
                                       other * math.sin(i*math.tau/20))) for i in range(20))
    faces = [(i, (i+1) % 20, 20+(i+1) % 20, 20+i) for i in range(20)]
    faces.extend([tuple(reversed(range(20))), tuple(range(20, 40))])
    return _mesh(actor, name, verts, faces, mat, [{bone.name: 1}] * 40)


def _box(actor, name, center, size, mat, bone):
    verts = [(center[0]+x*size[0]/2, center[1]+y*size[1]/2, center[2]+z*size[2]/2)
             for x, y, z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                             (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    return _mesh(actor, name, verts,
                 [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],
                 mat, [{bone.name: 1}] * 8)


def _point(actor, bone, tail=False):
    return actor.rig.matrix_local @ (bone.tail_local if tail else bone.head_local)


def _retain_skin(actor):
    """Delete original clothing geometry, including hidden body below the collar.

    Preserve only head/neck and hands by dominant skinning group. This also
    removes shoes, cuffs and military accessories rather than covering them.
    """
    import bmesh
    allowed = {b.name for b in actor.rig.data.bones
               if any(t in _bone_key(b.name) for t in ('head', 'neck', 'finger', 'thumb', 'hand'))}
    for obj in actor.imported:
        if obj.type != 'MESH':
            continue
        names = {g.index: g.name for g in obj.vertex_groups}
        keep = set()
        for v in obj.data.vertices:
            if v.groups and names.get(max(v.groups, key=lambda g: g.weight).group) in allowed:
                keep.add(v.index)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context='VERTS')
        bm.to_mesh(obj.data)
        bm.free()


def _wardrobe(actor, ctx):
    rig = actor.rig
    hips = _bone(rig, 'hips', 'pelvis', 'bip01')
    chest = _bone(rig, 'spine2', 'spine1', 'spine')
    head = _bone(rig, 'head')
    neck = _bone(rig, 'neck')
    p = _point(actor, hips)
    n = _point(actor, neck)
    h = _point(actor, head)
    heavy = actor.name == 'valjean'
    bishop = actor.name == 'bishop'
    width = .29 if heavy else .245
    wool = _cloth(ctx, actor.name + '_wool',
                  (.12,.085,.05) if heavy else ((.012,.012,.016) if bishop else (.018,.035,.085)),
                  key='cassock_black' if bishop else 'cloth_wool')
    leather = _cloth(ctx, actor.name + '_leather', (.045,.025,.015), roughness=.7)
    white = _cloth(ctx, actor.name + '_linen', (.72,.68,.56))
    iron = _cloth(ctx, actor.name + '_iron', (.12,.13,.14), roughness=.55, metallic=.85)
    # Long coat skirt follows pelvis, torso follows spine. Overlap hides join.
    _ring(actor, 'coat_skirt', [(p.x,p.y,.16 if bishop else .49,width*1.42,.24),
                              (p.x,p.y,p.z-.03,width,.18),
                              (p.x,p.y,p.z+.14,width,.19)], wool, hips)
    _ring(actor, 'coat_bodice', [(p.x,p.y,p.z-.06,width,.19),
                               (n.x,n.y,n.z-.12,width*1.1,.20),
                               (n.x,n.y,n.z+.015,.115,.115)], wool, chest)
    _ring(actor, 'collar', [(n.x,n.y,n.z-.02,.12,.12),
                          (n.x,n.y,n.z+.055,.11,.11)], white if bishop else wool, neck)
    for side in ('left', 'right'):
        upper = _bone(rig, side+'arm', side+'upperarm')
        fore = _bone(rig, side+'forearm', side+'lowerarm')
        hand = _bone(rig, side+'hand')
        _tube(actor, side+'_sleeve_upper', _point(actor,upper), _point(actor,fore),
              .115 if heavy else .10, wool, upper)
        _tube(actor, side+'_sleeve_cuff', _point(actor,fore), _point(actor,hand),
              .092, wool, fore, .073)
        leg = _bone(rig, side+'upleg', side+'thigh')
        shin = _bone(rig, side+'leg', side+'calf')
        foot = _bone(rig, side+'foot')
        _tube(actor, side+'_breeches', _point(actor,leg), _point(actor,shin), .12, wool, leg)
        _tube(actor, side+'_boot', _point(actor,shin), _point(actor,foot), .085, leather, shin)
        fp = _point(actor,foot)
        _box(actor, side+'_boot_toe', (fp.x,fp.y-.075,.065), (.16,.29,.13), leather, foot)
    if heavy:
        _ring(actor, 'shoulder_cape', [(n.x,n.y,n.z-.40,.41,.28),
                                     (n.x,n.y,n.z-.13,.36,.25),
                                     (n.x,n.y,n.z+.015,.12,.12)], wool, chest)
        _ring(actor, 'hat_brim', [(h.x,h.y,h.z+.17,.39,.34),
                                (h.x,h.y,h.z+.185,.39,.34)], leather, head)
        _ring(actor, 'hat_crown', [(h.x,h.y,h.z+.18,.17,.155),
                                 (h.x,h.y,h.z+.34,.15,.14),
                                 (h.x,h.y,h.z+.35,.001,.001)], wool, head)
        _box(actor, 'knapsack', (p.x,p.y+.30,p.z+.23), (.40,.20,.48), leather, chest)
        for x in (-.15,.15):
            _tube(actor, 'knapsack_strap', (p.x+x,p.y-.205,p.z),
                  (n.x+x,n.y-.21,n.z-.14), .022, leather, chest)
        hand = _bone(rig, 'righthand')
        hp = _point(actor,hand)
        _tube(actor, 'walking_stick', hp+Vector((0,0,-.85)), hp+Vector((0,0,.25)), .022, leather, hand)
        _tube(actor, 'iron_ferrule', hp+Vector((0,0,-.88)), hp+Vector((0,0,-.77)), .026, iron, hand)
    elif bishop:
        # White side/back hair, open face and receding crown.
        hair = _cloth(ctx, 'bishop_white_hair', (.82,.80,.74))
        verts, faces = [], []
        for z, radius in ((h.z-.015,.145),(h.z+.12,.16),(h.z+.24,.10)):
            for i in range(25):
                angle = -.1 + i*(math.pi+.2)/24
                verts.append((h.x+radius*math.cos(angle),h.y+radius*math.sin(angle),z))
        for j in range(2):
            faces.extend((j*25+i,j*25+i+1,(j+1)*25+i+1,(j+1)*25+i) for i in range(24))
        _mesh(actor, 'white_hair', verts, faces, hair, [{head.name:1}]*len(verts))
    else:
        for sign in (-1,1):
            # Flat leather crossbelts across chest rather than round ropes.
            a = (p.x-sign*.18,p.y-.215,p.z+.01)
            b = (n.x+sign*.18,n.y-.225,n.z-.15)
            verts = [(a[0]-.025,a[1],a[2]),(a[0]+.025,a[1],a[2]),
                     (b[0]+.025,b[1],b[2]),(b[0]-.025,b[1],b[2])]
            _mesh(actor, 'crossbelt', verts, [(0,1,2,3)], white, [{chest.name:1}]*4)
        _ring(actor, 'bicorne_crown', [(h.x,h.y,h.z+.16,.16,.14),
                                     (h.x,h.y,h.z+.32,.09,.08),
                                     (h.x,h.y,h.z+.34,.001,.001)], wool, head)
        # Two upturned broad leaves, points worn across the shoulders.
        for sign in (-1,1):
            verts = [(h.x-.35,h.y,h.z+.18),(h.x+.35,h.y,h.z+.18),
                     (h.x+.19,h.y+sign*.10,h.z+.37),(h.x-.19,h.y+sign*.10,h.z+.37)]
            _mesh(actor, 'bicorne_leaf', verts, [(0,1,2,3)], wool, [{head.name:1}]*4)


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
        target = {_bone_key(b.name): b for b in actor.rig.data.bones}
        mapping = {}
        for bone in source.data.bones:
            key = _bone_key(bone.name)
            if key not in target:
                raise RuntimeError(f'[actors] incompatible clip bone {bone.name}: {clip}')
            mapping[bone.name] = target[key].name
            # Shared skeleton expected: direct quaternion curves require the
            # same local bone basis. Reject rather than silently twist limbs.
            a, b = bone.matrix_local.to_quaternion(), target[key].matrix_local.to_quaternion()
            if a.rotation_difference(b).angle > .02:
                raise RuntimeError(f'[actors] rest basis mismatch for {bone.name}: {clip}')
        result = action.copy()
        result.name = f'AN_{actor.name}_{clip}'
        for curve in list(result.fcurves):
            match = re.match(r'pose\.bones\["(.+?)"\](.*)', curve.data_path)
            if not match or match.group(2) == '.scale':
                result.fcurves.remove(curve)
                continue
            bone_name, suffix = match.groups()
            if bone_name not in mapping:
                raise RuntimeError(f'[actors] unmapped curve {curve.data_path}')
            curve.data_path = f'pose.bones["{mapping[bone_name]}"]{suffix}'
            # In-place policy: lock horizontal root channels in the bone's
            # own rest basis, retaining vertical bob. Imported local Y may
            # be vertical, so do not assume location channel Z is world up.
            if suffix == '.location' and any(t in _bone_key(bone_name) for t in ('hips','pelvis','root')):
                basis = source.matrix_world.to_3x3() @ source.data.bones[bone_name].matrix_local.to_3x3()
                axis = basis.col[curve.array_index].normalized()
                if abs(axis.z) < .5:
                    for point in curve.keyframe_points:
                        point.co.y = 0
            for point in curve.keyframe_points:
                point.interpolation = 'BEZIER'
                point.handle_left_type = point.handle_right_type = 'AUTO_CLAMPED'
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
    strip.extrapolation = 'NOTHING'
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
            offset.z = .72
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
        _textures(objects, asset['textures'])
        _retain_skin(actor)
        _wardrobe(actor, ctx)
        # Flag hidden until a shot supplies its motivated key light.
        black = _cloth(ctx, name+'_negative_fill', (.002,.002,.002))
        flag = _box(actor, 'face_flag', (0,0,0), (.42,.48,.012), black, _bone(rig,'head'))
        flag.modifiers.clear()
        flag.vertex_groups.clear()
        flag.visible_camera = False
        flag.visible_glossy = False
        flag.hide_render = True
        actor.flag = flag
        ACTORS[name] = actor
        print(f'[actors] imported {name}: {avatar}; period wardrobe fitted', flush=True)
    ctx.cast = ACTORS
    return ACTORS
