"""Meter-scale hero props for Blender 4.2; no downloads or timeline assumptions.

All roots sit on their support surface, +Z up. Shots may reparent roots to hands;
children keep local transforms. Key flame light.data.energy and flame.hide_render
at ctx.frame(ctx.cue(...)); this module deliberately creates no timed animation.
"""
import math
import random

import bpy

PROP_ANCHORS = {
    'dining_room': {'origin': (60, -4, 0), 'space': 'relative to room origin',
                    'candlestick_1': (-.42, 0, .79), 'candlestick_2': (.42, 0, .79),
                    'wicker_basket': (.65, .30, .79), 'rye_loaf': (0, -.25, .79),
                    'wine_bottle': (-.70, .25, .79),
                    'place_settings': [(-.60 + .60 * i, y, .79)
                                       for y in (-.45, .45) for i in range(3)]},
    'bedroom': {'origin': (60, -4, 0), 'space': 'relative; align to world cupboard anchor',
                'wicker_basket': (1.65, 2.0, 1.05),
                'iron_candlestick': (.60, 2.0, .65)},
    'attachments': {'candlestick_1': (0, 0, .12),
                    'candlestick_2': (0, 0, .12),
                    'iron_candlestick': (0, 0, .09),
                    'wicker_basket': (0, 0, .255),
                    'yellow_passport': (0, -.07, 0)},
}


def _material(name, color, rough=.6, metal=0, noise_scale=70):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    n, l = mat.node_tree.nodes, mat.node_tree.links
    n.clear()
    out = n.new('ShaderNodeOutputMaterial')
    bs = n.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Roughness'].default_value = rough
    noise = n.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = noise_scale
    noise.inputs['Detail'].default_value = 3
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*(v * .62 for v in color), 1)
    ramp.color_ramp.elements[1].color = (*color, 1)
    l.new(noise.outputs['Fac'], ramp.inputs[0])
    l.new(ramp.outputs['Color'], bs.inputs['Base Color'])
    bump = n.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .16
    bump.inputs['Distance'].default_value = .00018
    l.new(noise.outputs['Fac'], bump.inputs['Height'])
    l.new(bump.outputs[0], bs.inputs['Normal'])
    l.new(bs.outputs[0], out.inputs[0])
    return mat


def _silver():
    mat = _material('PROP_polished_silver', (.94, .92, .86), .19, 1, 220)
    n, l = mat.node_tree.nodes, mat.node_tree.links
    bs = next(x for x in n if x.type == 'BSDF_PRINCIPLED')
    noise = next(x for x in n if x.type == 'TEX_NOISE')
    rough = n.new('ShaderNodeMapRange')
    rough.inputs['To Min'].default_value = .15
    rough.inputs['To Max'].default_value = .25
    l.new(noise.outputs['Fac'], rough.inputs['Value'])
    l.new(rough.outputs[0], bs.inputs['Roughness'])
    attr = n.new('ShaderNodeAttribute')
    attr.attribute_name = 'crevice'
    mix = n.new('ShaderNodeMixRGB')
    mix.inputs[1].default_value = (.94, .92, .86, 1)
    mix.inputs[2].default_value = (.10, .075, .045, 1)
    l.new(attr.outputs['Fac'], mix.inputs[0])
    l.new(mix.outputs[0], bs.inputs['Base Color'])
    return mat


def _object(col, name, data=None, parent=None, loc=(0, 0, 0)):
    obj = bpy.data.objects.new(name, data)
    col.objects.link(obj)
    obj.parent = parent
    obj.location = loc
    return obj


def _mesh(col, name, verts, faces, mat, parent=None):
    mesh = bpy.data.meshes.new(name + '_mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = _object(col, name, mesh, parent)
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def _lathe(col, name, profile, mat, parent=None, segments=64):
    # profile entries: radius, height, optional explicit crevice weight.
    verts, faces = [], []
    for row in profile:
        r, z = row[:2]
        for j in range(segments):
            a = math.tau * j / segments
            flute = 1 + (.015 * math.cos(16 * a) if .06 < z < .145 else 0)
            verts.append((r * math.cos(a) * flute, r * math.sin(a) * flute, z))
    for i in range(len(profile) - 1):
        for j in range(segments):
            a = i * segments + j
            b = i * segments + (j + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    obj = _mesh(col, name, verts, faces, mat, parent)
    attr = obj.data.attributes.new('crevice', 'FLOAT', 'POINT')
    for i, row in enumerate(profile):
        for j in range(segments):
            attr.data[i * segments + j].value = row[2] * .72 if len(row) > 2 else 0
    return obj


def _tube(col, name, points, radius, mat, parent=None, cyclic=False):
    curve = bpy.data.curves.new(name + '_curve', 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth, curve.bevel_resolution = radius, 2
    spline = curve.splines.new('POLY')
    spline.points.add(len(points) - 1)
    for p, xyz in zip(spline.points, points):
        p.co = (*xyz, 1)
    spline.use_cyclic_u = cyclic
    obj = _object(col, name, curve, parent)
    curve.materials.append(mat)
    return obj


def _ellipsoid(col, name, scale, mat, parent=None, loc=(0, 0, 0)):
    # Closed lathe with actual geometry scale, no operator/context dependency.
    profile = [(math.sin(math.pi * i / 24), math.cos(math.pi * i / 24))
               for i in range(25)]
    obj = _lathe(col, name, list(reversed(profile)), mat, parent, 48)
    obj.scale, obj.location = scale, loc
    return obj


PROFILE = [(0, 0, .2), (.056, 0, .1), (.0565, .004, .05),
           (.054, .008, .55), (.051, .011, .1), (.046, .016, .65),
           (.043, .020, .12), (.036, .025, .5), (.027, .031, .2),
           (.019, .036, .85), (.024, .041, .08), (.025, .046, .05),
           (.022, .051, .45), (.015, .056, .88), (.017, .064, .2),
           (.0185, .082, .12), (.0205, .102, .08), (.0235, .122, .05),
           (.0255, .136, .04), (.023, .144, .35), (.0145, .150, .9),
           (.019, .154, .12), (.015, .158, .82), (.0185, .168, .15),
           (.0195, .182, .1), (.021, .194, .55), (.032, .199, .25),
           (.037, .204, .06), (.035, .207, .4), (.023, .202, .85),
           (.0185, .205, .7), (.020, .211, .3), (.0295, .215, .08),
           (.031, .218, .04), (.028, .220, .2), (.018, .216, .82),
           (.013, .215, .9)]


def _candle(col, root, wax, wick, flame_mat, bottom, height):
    name = root.name
    _lathe(col, name + '_candle', [(0, bottom), (.011, bottom),
           (.0118, bottom + height * .6), (.010, bottom + height),
           (.006, bottom + height - .002), (0, bottom + height - .002)], wax, root)
    for i in range(4):
        a = i * 2.1
        _tube(col, name + '_wax_drip_%02d' % i,
              [(math.cos(a) * .011, math.sin(a) * .011, bottom + height - j * .004)
               for j in range(3 + i)], .0013, wax, root)
    top = bottom + height
    _tube(col, name + '_wick', [(0, 0, top - .002), (.001, 0, top + .005)], .0007, wick, root)
    flame = _lathe(col, name + '_flame', [(0, 0), (.003, .003), (.004, .008),
                   (.0025, .016), (0, .028)], flame_mat, root, 24)
    flame.location.z = top + .004
    data = bpy.data.lights.new(name + '_flame_light', 'POINT')
    data.energy, data.color, data.shadow_soft_size = 1.2, (1, .48, .15), .012
    light = _object(col, name + '_flame_light', data, root, (0, 0, top + .016))
    root['flame_object'], root['flame_light'] = flame.name, light.name
    root['lighting_control'] = 'key data.energy; key flame hide_render at timing cues'


def _bowl(col, name, mat, parent=None, radius=.085, height=.045):
    # Open vessel with modeled inner surface and rounded lip.
    profile = [(0, .003), (.40, .003), (.64, .13), (.87, .55),
               (1, .94), (1, 1), (.96, 1.01), (.92, .94),
               (.81, .55), (.58, .18), (.35, .10), (0, .10)]
    return _lathe(col, name, [(r * radius, z * height) for r, z in profile], mat, parent)


def _passport(col, ctx, paper):
    """Packed generated paper/stamp map; italic OFL font curves for crisp ink."""
    rng = random.Random(1815)
    size = 512
    pixels = []
    for y in range(size):
        for x in range(size):
            u, v = x / size, y / size
            grain = rng.uniform(-.025, .025)
            crease = .07 * math.exp(-((u - .5) / .008) ** 2)
            color = (.78 + grain - crease, .59 + grain - crease, .22 + grain - crease)
            d = math.hypot((u - .78), (v - .22))
            stamp = (.070 < d < .078 or .057 < d < .060 or
                     (abs(u - .78) < .004 and abs(v - .22) < .045) or
                     (abs(v - .22) < .004 and abs(u - .78) < .035))
            if stamp and rng.random() > .09:
                color = (.42 + grain, .035, .022)
            pixels.extend((*color, 1))
    image = bpy.data.images.new('passport_generated_paper_and_red_stamp', size, size)
    image.pixels.foreach_set(pixels)
    image.pack()
    n, l = paper.node_tree.nodes, paper.node_tree.links
    bs = next(node for node in n if node.type == 'BSDF_PRINCIPLED')
    tex = n.new('ShaderNodeTexImage')
    tex.image = image
    l.new(tex.outputs['Color'], bs.inputs['Base Color'])
    root = _object(col, 'yellow_passport')
    mesh = _mesh(col, 'passport_paper', [(-.105, -.145, 0), (.105, -.145, .001),
                 (.105, .145, 0), (-.105, .145, .002)], [(0, 1, 2, 3)], paper, root)
    uv = mesh.data.uv_layers.new(name='UVMap')
    for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        loop.uv = co
    solid = mesh.modifiers.new('paper_thickness', 'SOLIDIFY')
    solid.thickness = .00025
    ink = _material('PROP_passport_ink', (.055, .033, .014), .85)
    font = bpy.data.fonts.load(ctx.assets.font('garamond_italic'), check_existing=True)
    for i, text in enumerate(('Jean Valjean', 'forçat libéré', '19 ans au bagne')):
        curve = bpy.data.curves.new('passport_line_%d' % i, 'FONT')
        curve.body, curve.font, curve.size = text, font, .019
        curve.shear = .15
        curve.space_character = 1.08
        obj = _object(col, 'passport_text_%d' % i, curve, root, (-.088, .085 - i * .045, .003))
        obj.rotation_euler.z = (.012, -.018, .009)[i]
        curve.materials.append(ink)
    root['text'] = 'Jean Valjean | forçat libéré | 19 ans au bagne'
    return root


def build(ctx):
    """Create props and expose ctx.props (name -> root); safe to rebuild PROPS."""
    col = ctx.col('PROPS')
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    silver = _silver()
    iron = _material('PROP_forged_iron', (.095, .078, .06), .68, 1)
    wax = _material('PROP_beeswax', (.72, .53, .25), .37)
    wax.node_tree.nodes.get('Principled BSDF').inputs['Subsurface Weight'].default_value = .06
    wick = _material('PROP_charred_wick', (.012, .008, .004), .95)
    flame_mat = _material('PROP_flame_emission', (1, .55, .16), .3)
    bs = flame_mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Emission Color'].default_value = (1, .52, .12, 1)
    bs.inputs['Emission Strength'].default_value = 5
    wicker = _material('PROP_willow', (.27, .13, .045), .67, noise_scale=145)
    ceramic = _material('PROP_glazed_earthenware', (.32, .19, .09), .25)
    crust = _material('PROP_rye_crust', (.25, .105, .029), .88, noise_scale=95)
    paper = _material('PROP_yellow_paper', (.78, .59, .22), .9)
    roots = {}
    for i in range(1, 3):
        name = 'candlestick_%d' % i
        root = roots[name] = _object(col, name)
        _lathe(col, name + '_silver_body', PROFILE, silver, root)
        _candle(col, root, wax, wick, flame_mat, .214, .095)
    root = roots['iron_candlestick'] = _object(col, 'iron_candlestick')
    _lathe(col, 'iron_candlestick_body', [(0, 0), (.047, 0), (.048, .008),
           (.016, .018), (.009, .03), (.009, .11), (.021, .12),
           (.022, .138), (.014, .14)], iron, root)
    _tube(col, 'iron_candlestick_handle', [(.02 + .032 * math.cos(a), 0, .065 + .04 * math.sin(a))
          for a in [math.tau * i / 48 for i in range(48)]], .003, iron, root, True)
    _candle(col, root, wax, wick, flame_mat, .135, .065)
    basket = roots['wicker_basket'] = _object(col, 'wicker_basket')
    for j in range(13):
        z = .006 + j * .0065
        _tube(col, 'basket_weft_%02d' % j,
              [((.142 + z * .20) * math.cos(a), (.090 + z * .18) * math.sin(a),
                z + .001 * math.sin(32 * a)) for a in [math.tau * i / 128 for i in range(128)]],
              .0021, wicker, basket, True)
    for j in range(32):
        a = math.tau * j / 32
        _tube(col, 'basket_stake_%02d' % j,
              [((.142 + z * .20 + .0015 * math.sin(k * math.pi)) * math.cos(a),
                (.090 + z * .18 + .0015 * math.sin(k * math.pi)) * math.sin(a), z)
               for k, z in enumerate([i * .00325 for i in range(28)])], .002, wicker, basket)
    for j in range(-13, 14):
        x = j * .01
        y = .089 * math.sqrt(max(0, 1 - (x / .142) ** 2))
        _tube(col, 'basket_base_%02d' % (j + 13), [(x, -y, .004), (x, y, .004)], .003, wicker, basket)
    _tube(col, 'basket_handle', [(.158 * math.cos(a), 0, .085 + .17 * math.sin(a))
          for a in [math.pi * i / 64 for i in range(65)]], .005, wicker, basket)
    cutlery = roots['silverware'] = _object(col, 'silverware', parent=basket)
    for kind in ('fork', 'spoon'):
        for i in range(6):
            name = '%s_%d' % (kind, i + 1)
            root = roots[name] = _object(col, name, parent=cutlery,
                   loc=(-.025 if kind == 'fork' else .025, (i - 2.5) * .011, .017 + i * .004))
            root.rotation_euler = (.06, -.08, (i - 2.5) * .065 + (0 if kind == 'fork' else math.pi))
            _tube(col, name + '_handle', [(-.100, 0, 0), (-.085, 0, .001),
                  (-.03, 0, .002), (.035, 0, .005)], .003, silver, root)
            _ellipsoid(col, name + '_handle_tip', (.013, .006, .002), silver, root, (-.09, 0, 0))
            if kind == 'fork':
                _ellipsoid(col, name + '_shoulder', (.018, .012, .002), silver, root, (.042, 0, .006))
                for t in range(4):
                    _tube(col, name + '_tine_%d' % t, [(.043, (t - 1.5) * .006, .006),
                          (.073, (t - 1.5) * .006, .008), (.087, (t - 1.5) * .006, .012)], .0012, silver, root)
            else:
                bowl = _bowl(col, name + '_bowl', silver, root, .017, .005)
                bowl.scale.x = 1.5
                bowl.location = (.060, 0, .004)
    root = roots['ladle'] = _object(col, 'ladle', parent=cutlery, loc=(0, 0, .052))
    root.rotation_euler.z = .55
    _tube(col, 'ladle_handle', [(-.14, 0, .015), (-.08, 0, .025), (.04, 0, .035), (.09, 0, .012)], .004, silver, root)
    bowl = _bowl(col, 'ladle_cup', silver, root, .035, .022)
    bowl.location = (.10, 0, 0)
    roots['yellow_passport'] = _passport(col, ctx, paper)
    for name, scale in [('rye_loaf', (.15, .14, .075)), ('bakery_loaf', (.25, .085, .06))]:
        root = roots[name] = _object(col, name)
        _ellipsoid(col, name + '_crust', scale, crust, root, (0, 0, scale[2]))
        # Shallow dark scores follow the curved upper crust.
        for i in range(-2, 3):
            x = i * scale[0] * .23
            pts = [(x + t * .015, t * scale[1] * .6,
                    scale[2] * (1 + math.sqrt(max(0, 1 - (x / scale[0]) ** 2 - (t * .6) ** 2))) + .0004)
                   for t in [-1 + k / 10 for k in range(21)]]
            _tube(col, name + '_score_%d' % (i + 2), pts, .0015, crust, root)
    for i in range(6):
        name = 'bowl_%d' % (i + 1)
        roots[name] = _bowl(col, name, ceramic)
    glass = _material('PROP_clear_glass', (.98, .99, 1), .065)
    bs = glass.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Transmission Weight'].default_value = 1
    bs.inputs['IOR'].default_value = 1.46
    bottle = _material('PROP_green_bottle_glass', (.05, .12, .025), .14)
    bs = bottle.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Transmission Weight'].default_value = .85
    bs.inputs['IOR'].default_value = 1.48
    roots['wine_bottle'] = _lathe(col, 'wine_bottle', [(0, 0), (.040, 0), (.044, .012),
          (.043, .18), (.038, .21), (.015, .24), (.014, .30), (.017, .305),
          (.017, .31), (.010, .31), (.010, .245), (.035, .205), (.038, .016), (0, .016)], bottle)
    for i in range(6):
        name = 'wine_glass_%d' % (i + 1)
        roots[name] = _lathe(col, name, [(0, 0), (.031, 0), (.032, .003), (.008, .006),
              (.004, .012), (.004, .06), (.019, .068), (.031, .09), (.033, .13),
              (.031, .131), (.029, .092), (.016, .072), (0, .069)], glass)
    chain = roots['iron_chain'] = _object(col, 'iron_chain')
    for j in range(26):
        points = []
        for i in range(32):
            a = math.tau * i / 32
            x, y = .023 * math.cos(a), .011 * math.sin(a)
            points.append((x, y, 0) if j % 2 == 0 else (x, 0, y))
        link = _tube(col, 'iron_chain_link_%02d' % j, points, .003, iron, chain, True)
        link.location = (j * .033, .015 * math.sin(j * .4), .016)
    # Initial dining layout; all other roots remain available for shot placement.
    dining = PROP_ANCHORS['dining_room']
    origin = dining['origin']
    for name in ('candlestick_1', 'candlestick_2', 'wicker_basket', 'rye_loaf', 'wine_bottle'):
        roots[name].location = tuple(a + b for a, b in zip(origin, dining[name]))
    for i, pos in enumerate(dining['place_settings'], 1):
        roots['bowl_%d' % i].location = tuple(a + b for a, b in zip(origin, pos))
        roots['wine_glass_%d' % i].location = (origin[0] + pos[0] + .16, origin[1] + pos[1], origin[2] + pos[2])
    ctx.props = roots
    ctx.prop_anchors = PROP_ANCHORS
    print('[props] built %d named roots in PROPS; passport texture packed' % len(roots))
    return roots
