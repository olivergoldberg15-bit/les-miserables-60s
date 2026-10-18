"""Shared deterministic scene and timing helpers (Blender 4.2)."""
import math
import re
from types import SimpleNamespace


def normalized(word):
    return re.sub(r'[^\w]', '', word.casefold())


class Context(SimpleNamespace):
    fps = 24

    def frame(self, seconds):
        return 1 + int(round(float(seconds) * self.fps))

    def cue(self, line_id, word, nth=1):
        matches = [w['s'] for line in self.timing['lines'] if line['id'] == line_id
                   for w in line['words'] if normalized(w['w']) == normalized(word)]
        if nth < 1 or nth > len(matches):
            raise KeyError(f'[cue] {line_id}:{word} occurrence {nth} not found')
        return matches[nth - 1]

    def shot_range(self, shot_id):
        lines = self.timing['lines']
        for i, line in enumerate(lines):
            if line['id'] == shot_id:
                start = (lines[i - 1]['end'] + line['start']) / 2 if i else 0
                end = (line['end'] + lines[i + 1]['start']) / 2 if i + 1 < len(lines) else self.timing['duration']
                return self.frame(start), min(self.frame(end) - 1, math.ceil(self.timing['duration'] * self.fps))
        raise KeyError(f'[shot_range] unknown shot {shot_id}')

    def col(self, name):
        import bpy
        collection = bpy.data.collections.get(name)
        if collection is None:
            collection = bpy.data.collections.new(name)
        if collection.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(collection)
        return collection


def look_at(obj, target):
    from mathutils import Vector
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def pbr_material(ctx, key, scale=1.0, name=None):
    import bpy
    material = bpy.data.materials.get(name or f'PBR_{key}_{scale}')
    if material:
        return material
    material = bpy.data.materials.new(name or f'PBR_{key}_{scale}')
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes.get('Principled BSDF')
    coords = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    mapping.inputs['Scale'].default_value = (scale,) * 3
    links.new(coords.outputs['Generated'], mapping.inputs['Vector'])
    maps = {}
    for channel, path in ctx.assets.texture(key).items():
        if not path:
            continue
        node = nodes.new('ShaderNodeTexImage')
        node.image = bpy.data.images.load(path, check_existing=True)
        node.projection = 'BOX'
        node.projection_blend = 0.2
        if channel != 'albedo':
            node.image.colorspace_settings.name = 'Non-Color'
        links.new(mapping.outputs['Vector'], node.inputs['Vector'])
        maps[channel] = node
    links.new(maps['albedo'].outputs['Color'], shader.inputs['Base Color'])
    links.new(maps['roughness'].outputs['Color'], shader.inputs['Roughness'])
    normal = nodes.new('ShaderNodeNormalMap')
    links.new(maps['normal'].outputs['Color'], normal.inputs['Color'])
    output = normal.outputs['Normal']
    if 'displacement' in maps:
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Distance'].default_value = 0.025
        links.new(maps['displacement'].outputs['Color'], bump.inputs['Height'])
        links.new(output, bump.inputs['Normal'])
        output = bump.outputs['Normal']
    links.new(output, shader.inputs['Normal'])
    return material


def set_time_of_day(ctx, scene, key):
    import bpy
    settings = {'dusk': ('dusk', .3, 1.5, (1, .58, .3)),
                'night': ('night', .08, .1, (.35, .48, 1)),
                'dawn': ('dawn', .35, 1.8, (1, .75, .5)),
                'interior_candle': ('interior', .025, 0, (1, .5, .2)),
                'interior_moon': ('night', .025, .08, (.35, .48, 1))}
    hdri, strength, energy, color = settings[key]
    world = bpy.data.worlds.get('World_' + key) or bpy.data.worlds.new('World_' + key)
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    env = nodes.get('Environment') or nodes.new('ShaderNodeTexEnvironment')
    env.name = 'Environment'
    env.image = bpy.data.images.load(ctx.assets.hdri(hdri), check_existing=True)
    background = nodes.get('Background')
    background.inputs['Strength'].default_value = strength
    links.new(env.outputs['Color'], background.inputs['Color'])
    scene.world = world
    sun = bpy.data.objects.get('TIME_SUN')
    if sun is None:
        sun = bpy.data.objects.new('TIME_SUN', bpy.data.lights.new('TIME_SUN', 'SUN'))
        scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(78), math.radians(-20), math.radians(-35))
    sun.data.energy, sun.data.color, sun.data.angle = energy, color, math.radians(8)
    return world
