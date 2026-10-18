"""Digne, metres/Z-up. Geometry only; shot timing belongs to shots.py.

All anchors are WORLD coordinates. Door objects have their origin at the hinge,
so shots can rotate them without rebuilding the set. Repeated architectural
parts share mesh datablocks; roof barrel courses are batched into one mesh.
"""
import math
from pathlib import Path
import random

import bpy
from mathutils import Vector

try:
    from . import lib
except ImportError:
    import lib


LOCATIONS = {
    "road": {"origin": (-180, -60, 9), "anchors": {
        "start": (-180, -60, 9), "bend": (-125, -34, 4), "gate": (-70, -8, 0)}},
    "town_gate": {"origin": (-70, -8, 0), "anchors": {"passage": (-70, -8, 0)}},
    "main_street": {"origin": (-70, -8, 0), "anchors": {
        "west": (-70, -8, 0), "east": (0, 0, 0), "passport": (-51, -5, 0),
        "dawn_start": (22, -7, 0), "dawn_end": (60, -10, 0)}},
    "inn": {"origin": (-45, 4, 0), "anchors": {"door": (-45, 0, 0), "threshold": (-45, -0.3, 0)}},
    "prison": {"origin": (-25, -7, 0), "anchors": {
        "door": (-25, -3, 0), "wicket": (-25, -2.82, 1.55), "bell": (-23.8, -2.7, 2.4)}},
    "kennel": {"origin": (-12, 6, 0), "anchors": {"entrance": (-12, 2, 0), "eyes": (-12, 6.4, 0.55)}},
    "cathedral": {"origin": (0, 22, 0), "anchors": {"door": (0, 10, 0), "clock": (8, 17.8, 28)}},
    "hospital": {"origin": (90, 0, 0), "anchors": {"door": (90, -8, 0), "garden": (90, 17, 0)}},
    "bishop_house": {"origin": (60, -4, 0), "anchors": {
        "door": (57, -9, 0), "threshold": (57, -9.4, 0), "hall": (57, -7, 0)}},
    "dining_room": {"origin": (57, -4, 0), "anchors": {
        "table": (57, -3.8, 0.79), "fireplace": (54.4, -2, 0),
        "mantel": (54.7, -2, 1.45), "bishop_chair": (55.7, -3.8, 0),
        "valjean_chair": (58.3, -3.8, 0), "door": (57, -9, 0)}},
    "bishop_bedroom": {"origin": (63, -1, 0), "anchors": {
        "bed": (63.7, -1.2, 0.52), "pillow": (63.7, 0.1, 0.8),
        "cupboard": (60.6, -0.8, 0), "silver": (60.8, -0.8, 1.15),
        "window": (63, 1, 1.8), "valjean": (62.1, -1.2, 0)}},
    "guest_alcove": {"origin": (63, -6, 0), "anchors": {
        "bed": (64, -6, 0.5), "pillow": (64, -4.9, 0.78), "window": (66, -6, 1.8)}},
    "garden": {"origin": (60, 10, 0), "anchors": {
        "bed": (63, 14, 0.15), "basket_landing": (63, 14, 0.2),
        "vault": (60, 19, 2.2), "escape": (60, 21, 0), "door": (57, 1, 0)}},
    "bakery_flashback": {"origin": (-240, 90, 0), "anchors": {
        "window": (-240, 86, 1.5), "loaf": (-240, 86.4, 1.2), "street": (-240, 84.5, 0)}},
    "galley_flashback": {"origin": (-240, 125, 0), "anchors": {
        "hands": (-240, 124, 1), "tallies": (-243.7, 125, 1.4), "window": (-240, 129, 2.5)}},
}

LOOKDEV_CAMERAS = {
    "road": {"loc": (-158, -82, 29), "target": (-65, -5, 4), "lens_mm": 32, "time": "dusk"},
    "town_gate": {"loc": (-88, -20, 3), "target": (-70, -8, 3), "lens_mm": 35, "time": "dusk"},
    "main_street": {"loc": (-65, -7, 2), "target": (-20, -1, 3), "lens_mm": 30, "time": "night"},
    "inn": {"loc": (-46, -9, 2.2), "target": (-45, 0, 2), "lens_mm": 38, "time": "night"},
    "prison": {"loc": (-25, 3, 1.8), "target": (-25, -3, 1.5), "lens_mm": 36, "time": "night"},
    "kennel": {"loc": (-12, 2.3, 1.1), "target": (-12, 6.8, 0.6), "lens_mm": 35, "time": "night"},
    "cathedral": {"loc": (-24, -24, 16), "target": (2, 23, 17), "lens_mm": 34, "time": "night"},
    "hospital": {"loc": (111, -34, 11), "target": (90, 0, 6), "lens_mm": 40, "time": "dawn"},
    "bishop_house": {"loc": (49, -22, 4), "target": (60, -4, 3), "lens_mm": 40, "time": "dusk"},
    "dining_room": {"loc": (59.3, -7.6, 1.65), "target": (56, -2.6, 1.1), "lens_mm": 24, "time": "interior_candle"},
    "bishop_bedroom": {"loc": (60.7, -2.6, 1.65), "target": (63.6, -0.7, 1), "lens_mm": 24, "time": "interior_moon"},
    "guest_alcove": {"loc": (60.8, -8.2, 1.5), "target": (64, -5.7, 0.8), "lens_mm": 24, "time": "interior_moon"},
    "garden": {"loc": (53, 4, 3), "target": (61, 16, 1.2), "lens_mm": 30, "time": "night"},
    "bakery_flashback": {"loc": (-240, 82, 1.7), "target": (-240, 86, 1.5), "lens_mm": 40, "time": "night"},
    "galley_flashback": {"loc": (-237, 122, 1.6), "target": (-241, 127, 1.5), "lens_mm": 28, "time": "interior_moon"},
}


class Town:
    def __init__(self, ctx):
        self.ctx = ctx
        self.meshes = {}
        self.assets = {}
        self.rng = random.Random(1815)
        self.col = None
        self.mats = {k: lib.pbr_material(ctx, k) for k in (
            "plaster", "limestone_wall", "rubble_stone", "cobblestone",
            "roof_tiles", "wood_planks", "dirt_road", "dry_grass", "forest_floor", "cloth_wool")}
        # Metal/glass remain texture-derived; no untextured default surfaces.
        for name, source, metal, rough, transmission in (
            ("iron", "limestone_wall", 1, .65, 0),
            ("glass", "plaster", 0, .12, 1),
        ):
            mat = self.mats[source].copy()
            mat.name = "MAT_world_" + name
            bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            for socket, value in (("Metallic", metal), ("Roughness", rough), ("Transmission Weight", transmission)):
                if socket in bsdf.inputs:
                    # Texture still drives albedo/normal, roughness deliberately overridden.
                    for link in list(bsdf.inputs[socket].links):
                        mat.node_tree.links.remove(link)
                    bsdf.inputs[socket].default_value = value
            self.mats[name] = mat

    def location(self, name):
        self.col = self.ctx.col(name)
        self.col["world_location"] = name
        self.col["origin"] = LOCATIONS[name]["origin"]

    def memory_grade(self):
        """Desaturate copied, texture-derived masters only on the memory set."""
        materials, meshes = {}, {}
        for obj in self.col.objects:
            if obj.type != "MESH":
                continue
            source = obj.data
            if source not in meshes:
                mesh = source.copy()
                for i, original in enumerate(mesh.materials):
                    if original not in materials:
                        mat = original.copy()
                        mat.name = "MAT_memory_" + original.name
                        nodes, links = mat.node_tree.nodes, mat.node_tree.links
                        bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
                        color = bsdf.inputs["Base Color"]
                        grade = nodes.new("ShaderNodeHueSaturation")
                        grade.inputs["Saturation"].default_value = .22
                        if color.links:
                            links.new(color.links[0].from_socket, grade.inputs["Color"])
                        else:
                            grade.inputs["Color"].default_value = color.default_value
                        links.new(grade.outputs["Color"], color)
                        materials[original] = mat
                    mesh.materials[i] = materials[original]
                meshes[source] = mesh
            obj.data = meshes[source]
        self.col["memory_saturation"] = .22

    def mesh(self, name, verts, faces, material):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.materials.append(self.mats[material])
        mesh.update()
        return mesh

    def obj(self, name, mesh, loc=(0, 0, 0)):
        obj = bpy.data.objects.new(name, mesh)
        self.col.objects.link(obj)
        obj.location = loc
        return obj

    def box(self, name, loc, size, material="plaster", bevel=0):
        key = ("box", tuple(size), material, bevel)
        if key not in self.meshes:
            x, y, z = (v / 2 for v in size)
            self.meshes[key] = self.mesh(name + "_mesh", [
                (-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)],
                [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], material)
        obj = self.obj(name, self.meshes[key], loc)
        if bevel:
            mod = obj.modifiers.new("worn_edges", "BEVEL")
            mod.width = bevel
            mod.segments = 1
        return obj

    def rod(self, name, a, b, radius, material="iron", sides=8):
        a, b = Vector(a), Vector(b)
        length = (b - a).length
        key = ("rod", round(length, 5), radius, material, sides)
        if key not in self.meshes:
            verts = [(radius * math.cos(i * math.tau / sides), radius * math.sin(i * math.tau / sides), z)
                     for z in (-length / 2, length / 2) for i in range(sides)]
            faces = [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
            faces += [(i, (i + 1) % sides, (i + 1) % sides + sides, i + sides) for i in range(sides)]
            self.meshes[key] = self.mesh(name + "_mesh", verts, faces, material)
        obj = self.obj(name, self.meshes[key], (a + b) / 2)
        obj.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
        return obj

    def light(self, name, loc, watts, color, size=.25, target=None):
        data = bpy.data.lights.new("LGT_Key_" + name, "AREA" if target else "POINT")
        data.energy, data.color = watts, color
        if target:
            data.shape, data.size = "DISK", size
        else:
            data.shadow_soft_size = size
        col = self.ctx.col(self.col.name + "_LIGHTS")
        # A child rig follows the location collection's render visibility.
        if col.name not in self.col.children:
            self.col.children.link(col)
        if col.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(col)
        obj = bpy.data.objects.new(data.name, data)
        col.objects.link(obj)
        obj.location = loc
        if target:
            lib.look_at(obj, target)
        return obj

    def prop(self, key, name, loc, size, material="wood_planks"):
        """Optional CC0 assets normalized once and linked thereafter.

        A manifest's None means procedural fallback. A supplied broken path is
        an integration error and deliberately fails rather than hiding it.
        """
        if key not in self.assets:
            path = self.ctx.assets.model(key)
            if not path:
                self.assets[key] = None
            else:
                path = Path(path)
                before = set(bpy.data.objects)
                suffix = path.suffix.lower()
                if suffix == ".blend":
                    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
                        dst.objects = list(src.objects)
                    imported = [o for o in dst.objects if o and o.type == "MESH"]
                elif suffix in (".glb", ".gltf", ".fbx"):
                    if suffix == ".fbx":
                        bpy.ops.import_scene.fbx(filepath=str(path))
                    else:
                        bpy.ops.import_scene.gltf(filepath=str(path))
                    imported = [o for o in set(bpy.data.objects) - before if o.type == "MESH"]
                else:
                    raise ValueError("[world] Unsupported model: " + str(path))
                if not imported:
                    raise ValueError("[world] Model contains no meshes: " + str(path))
                bpy.context.view_layer.update()
                verts, faces = [], []
                for obj in imported:
                    offset = len(verts)
                    verts.extend(tuple(obj.matrix_world @ v.co) for v in obj.data.vertices)
                    faces.extend(tuple(offset + i for i in p.vertices) for p in obj.data.polygons)
                low = [min(v[i] for v in verts) for i in range(3)]
                high = [max(v[i] for v in verts) for i in range(3)]
                verts = [tuple((v[i] - (low[i] + high[i]) / 2) / max(high[i] - low[i], .001)
                               for i in range(3)) for v in verts]
                self.assets[key] = self.mesh("asset_" + key, verts, faces, material)
                for obj in list(set(bpy.data.objects) - before):
                    bpy.data.objects.remove(obj, do_unlink=True)
        if self.assets[key] is None:
            return None
        obj = self.obj(name, self.assets[key], loc)
        obj.scale = size
        return obj

    def door(self, name, x, y, width=1.2, height=2.15, north=False):
        obj = self.box(name, (x, y, height / 2), (width, .12, height), "wood_planks", .015)
        # A unique translated mesh gives a stable left hinge without affecting instances.
        obj.data = obj.data.copy()
        for v in obj.data.vertices:
            v.co.x += width / 2
            v.co.z += height / 2
        obj.location = (x - width / 2, y, 0)
        obj["closed_rotation_z"] = 0.0
        for z in (.35, height - .35):
            bar = self.box(name + "_strap", (x, y + (.075 if north else -.075), z), (width, .035, .09), "iron")
            bar.parent = obj
            bar.location -= obj.location
        return obj

    def facade(self, name, x, y, width, height, north=False, door=False, floors=2):
        """Segment walls around real openings (no opaque wall behind glazing)."""
        sign = 1 if north else -1
        cols = max(1, int(width // 2.5))
        if cols % 2 == 0:
            cols -= 1  # Every main entrance stays on its exported centre anchor.
        cell, storey = width / cols, height / floors
        for floor in range(floors):
            for j in range(cols):
                cx = x - width / 2 + cell * (j + .5)
                isdoor = door and floor == 0 and j == cols // 2
                ww, bottom, top = (1.2, 0, 2.15) if isdoor else (1, floor * storey + 1, floor * storey + 2.25)
                base, cap = floor * storey, (floor + 1) * storey
                for dx in (-1, 1):
                    self.box(name + "_pier", (cx + dx * (ww + cell) / 4, y, (base + cap) / 2),
                             ((cell - ww) / 2, .4, storey))
                if bottom > base:
                    self.box(name + "_apron", (cx, y, (base + bottom) / 2), (ww, .4, bottom - base))
                self.box(name + "_lintel", (cx, y, (top + cap) / 2), (ww, .4, cap - top))
                if isdoor:
                    self.door(name + "_door", cx, y, north=north)
                    continue
                self.box(name + "_glass", (cx, y - sign * .12, (bottom + top) / 2), (ww, .025, top - bottom), "glass")
                self.box(name + "_sill", (cx, y + sign * .12, bottom), (1.2, .65, .13), "limestone_wall")
                self.box(name + "_mullion", (cx, y, (bottom + top) / 2), (.055, .1, top - bottom), "wood_planks")
                for side in (-1, 1):
                    shutter = self.box(name + "_shutter", (cx + side * .8, y + sign * .26, (bottom + top) / 2), (.47, .07, top - bottom), "wood_planks")
                    shutter.rotation_euler.z = side * .12
                    for zz in (bottom + .2, top - .2):
                        self.box(name + "_shutter_brace", (cx + side * .8, y + sign * .31, zz), (.46, .04, .07), "wood_planks")

    def roof(self, name, x, y, width, depth, eave):
        # Two pitched planes plus continuous half-cylinder barrel courses.
        rise = width * .27
        verts = [(x + sx * (width / 2 + .3), y + sy * (depth / 2 + .3), eave)
                 for sx in (-1, 1) for sy in (-1, 1)] + [(x, y - depth / 2 - .3, eave + rise), (x, y + depth / 2 + .3, eave + rise)]
        self.obj(name + "_roof", self.mesh(name + "_roofmesh", verts, [(0, 4, 5, 1), (4, 2, 3, 5)], "roof_tiles"))
        gables = [(x - width / 2, y + side * depth / 2, eave)
                  for side in (-1, 1)] + [(x + width / 2, y + side * depth / 2, eave)
                  for side in (-1, 1)] + [(x, y + side * depth / 2, eave + rise)
                  for side in (-1, 1)]
        self.obj(name + "_gables", self.mesh(name + "_gable_mesh", gables,
                 [(0, 2, 4), (3, 1, 5)], "plaster"))
        verts, faces = [], []
        # Texture carries individual joints; batched geometry carries the barrel silhouette.
        for yy in range(int((depth + .6) / .22)):
            cy = y - depth / 2 - .2 + yy * .22
            for side in (-1, 1):
                start = len(verts)
                for xx in (0, width / 2 + .3):
                    for k in range(7):
                        angle = math.pi * k / 6
                        verts.append((x + side * xx, cy + .11 * math.cos(angle), eave + rise * (1 - xx / (width / 2 + .3)) + .11 * math.sin(angle)))
                faces.extend((start + k, start + k + 7, start + k + 8, start + k + 1) for k in range(6))
        self.obj(name + "_barrel_courses", self.mesh(name + "_barrels", verts, faces, "roof_tiles"))

    def house(self, name, x, y, w=7, d=8, floors=2, front_north=False):
        h = floors * 2.8
        self.facade(name, x, y - d / 2, w, h, door=not front_north, floors=floors)
        self.facade(name + "_rear", x, y + d / 2, w, h, north=True, door=front_north, floors=floors)
        for side in (-1, 1):
            self.box(name + "_party_wall", (x + side * w / 2, y, h / 2), (.35, d, h))
            for end in (-1, 1):
                for z in range(int(h / .36)):
                    self.box(name + "_quoin", (x + side * (w / 2 + .015), y + end * (d / 2 + .025), .18 + z * .36),
                             (.48 if z % 2 else .65, .46, .32), "limestone_wall")
        self.box(name + "_floor", (x, y, -.08), (w, d, .16), "cobblestone")
        self.roof(name, x, y, w, d, h)
        self.box(name + "_chimney", (x + w * .28, y + d * .22, h + 1.1), (.65, .7, 2.2), "limestone_wall")
        self.box(name + "_chimney_cap", (x + w * .28, y + d * .22, h + 2.22), (.83, .85, .16), "roof_tiles")

    def lantern(self, name, x, y, z):
        if not self.prop("lantern", name, (x, y, z), (.3, .3, .5), "iron"):
            self.box(name + "_glass", (x, y, z), (.23, .23, .38), "glass")
            for dx in (-.14, .14):
                for dy in (-.14, .14):
                    self.rod(name + "_frame", (x + dx, y + dy, z - .23), (x + dx, y + dy, z + .23), .018)
            for zz in (z - .25, z + .25):
                self.box(name + "_cap", (x, y, zz), (.36, .36, .06), "iron")
        self.rod(name + "_bracket", (x, y + .45, z + .4), (x, y, z + .4), .025)
        self.light(name, (x, y, z), 24, (1, .46, .16), .08)

    def bed(self, name, x, y):
        self.box(name + "_frame", (x, y, .4), (1.3, 2.2, .22), "wood_planks", .02)
        self.box(name + "_mattress", (x, y, .6), (1.2, 2.1, .22), "cloth_wool", .06)
        self.box(name + "_blanket", (x, y - .25, .74), (1.24, 1.5, .1), "cloth_wool", .03)
        self.box(name + "_pillow", (x, y + .78, .79), (.83, .43, .17), "cloth_wool", .07)
        self.box(name + "_headboard", (x, y + 1.12, .7), (1.35, .12, 1.1), "wood_planks", .02)


def _landscape(t):
    t.location("road")
    t.box("town_ground", (0, 0, -.35), (410, 155, .6), "dry_grass")
    points = [(-180, -60, 9), (-155, -48, 6.7), (-125, -34, 4), (-95, -21, 1.6), (-70, -8, 0)]
    verts = []
    for x, y, z in points:
        verts.extend(((x, y - 3, z), (x, y + 3, z)))
    t.obj("descending_dirt_road", t.mesh("road_ribbon", verts, [(i, i + 2, i + 3, i + 1) for i in range(0, 8, 2)], "dirt_road"))
    # Continuous banks support every point on the rising road, not just hill peaks.
    banks = [(x, y + offset, -.1 if abs(offset) > 4 else z - .04)
             for x, y, z in points for offset in (-35, -3, 3, 35)]
    bank_faces = [(i * 4 + j, (i + 1) * 4 + j, (i + 1) * 4 + j + 1, i * 4 + j + 1)
                  for i in range(len(points) - 1) for j in range(3)]
    t.obj("continuous_road_banks", t.mesh("road_bank_mesh", banks, bank_faces, "dry_grass"))
    for a, b in zip(points, points[1:]):
        for side in (-1, 1):
            t.rod("roadside_rubble_wall", (a[0], a[1] + side * 4, a[2] + .25), (b[0], b[1] + side * 4, b[2] + .25), .35, "rubble_stone", 4)
        for offset in (-.85, .85):
            t.rod("wheel_rut", (a[0], a[1] + offset, a[2] + .012), (b[0], b[1] + offset, b[2] + .012), .07, "forest_floor", 4)
    # Low-poly hills underneath the raised road; mountains never hero-detail.
    for i, (x, y, z) in enumerate(points[:-1]):
        v = [(x - 35, y - 28, -.1), (x + 35, y - 28, -.1), (x + 35, y + 28, -.1), (x - 35, y + 28, -.1), (x, y, z - .06)]
        t.obj("dry_hill_%02d" % i, t.mesh("hill", v, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], "dry_grass"))
    for i in range(20):
        x, y = (-250 + i * 30, 180 + t.rng.uniform(-25, 60)) if i < 14 else (220 + t.rng.uniform(0, 50), (i - 14) * 40)
        h = t.rng.uniform(65, 135)
        v = [(x - 45, y - 30, -2), (x + 45, y - 30, -2), (x + 42, y + 30, -2), (x - 42, y + 30, -2), (x + 5, y, h)]
        t.obj("Alps_%02d" % i, t.mesh("mountain", v, [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], "limestone_wall"))
    for i in range(45):
        x, y = t.rng.uniform(-175, -85), t.rng.uniform(-66, -20)
        if not t.prop("rock_large", "road_rock", (x, y, .3), (.9, .7, .7), "limestone_wall"):
            obj = t.box("road_rock", (x, y, .25), (.8, .6, .5), "limestone_wall", .15)
            obj.rotation_euler.z = t.rng.random() * math.tau
        # Dry grass tufts share crossed, low-cost mesh geometry.
        for j in range(3):
            t.rod("dry_grass_stem", (x + 1, y, 0), (x + 1 + j * .08, y + .1, .35), .018, "dry_grass", 3)


def _street(t):
    t.location("town_gate")
    for y in (-14, -2):
        t.box("gate_tower", (-70, y, 4.8), (4, 5, 9.6), "rubble_stone", .08)
        t.roof("gate_tower", -70, y, 4.4, 5.4, 9.6)
    t.box("gate_lintel", (-70, -8, 6.5), (3, 7, 2), "limestone_wall")
    t.location("main_street")
    a, b = Vector((-70, -8, .025)), Vector((0, 0, .025))
    pavement = t.box("main_street_cobbles", (a + b) / 2, ((b - a).length, 6, .12), "cobblestone")
    pavement.rotation_euler.z = math.atan2(8, 70)
    t.box("cathedral_square", (4, 1, -.02), (26, 20, .16), "cobblestone")
    t.box("east_street", (48, -9.8, -.02), (80, 5, .16), "cobblestone")
    # Facade rows track the street slope; gaps reserved for the three hero sets.
    for i, x in enumerate(range(-63, -5, 7)):
        cy = -8 + (x + 70) * 8 / 70
        for side in (-1, 1):
            if (side == 1 and (abs(x + 45) < 7 or abs(x + 12) < 6)) or (side == -1 and abs(x + 25) < 7):
                continue
            t.house("street_house_%d_%d" % (i, side), x, cy + side * 7, 7, 8, 2 + i % 3, front_north=side < 0)
        if i % 2 == 0:
            t.lantern("street_lantern_%d" % i, x, cy + 2.7, 2.7)
    t.location("inn")
    t.house("inn", -45, 4, 9, 8, 3)
    t.lantern("inn_lantern", -43.7, -.5, 2.6)
    t.light("inn_window_spill", (-45, 1, 2), 120, (1, .5, .2), 1.3, (-45, -2, 1))
    sign = t.box("inn_hanging_sign", (-47, -1, 2.8), (1, .12, .7), "wood_planks", .03)
    sign["identity"] = "Jacquin Labarre"
    for x in (-48, -42):
        if not t.prop("barrel", "inn_barrel", (x, -.5, .5), (.65, .65, 1)):
            t.rod("inn_barrel", (x, -.5, 0), (x, -.5, 1), .34, "wood_planks", 12)
    t.location("prison")
    t.house("prison", -25, -7, 8, 8, 2, front_north=True)
    # Replace the generic front door with a framed opening and working wicket.
    door = bpy.data.objects.get("prison_rear_door")
    if door:
        for child in list(door.children):
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(door, do_unlink=True)
    # Facade centre depends on number of bays (8m / 3 bays); matches x=-25.
    t.box("prison_door_lower", (-25, -3, .63), (1.2, .16, 1.26), "wood_planks")
    t.box("prison_door_upper", (-25, -3, 1.96), (1.2, .16, .38), "wood_planks")
    for x in (-25.44, -24.56):
        t.box("prison_door_stile", (x, -3, 1.52), (.32, .16, .5), "wood_planks")
    wicket = t.box("prison_wicket", (-25, -2.86, 1.52), (.55, .06, .48), "iron")
    wicket["animation"] = "slide X to open"
    for z in (.35, 1.02, 1.9):
        t.box("prison_iron_strap", (-25, -2.9, z), (1.2, .04, .1), "iron")
    t.rod("prison_bell", (-23.8, -2.7, 2.25), (-23.8, -2.7, 2.55), .16, "iron", 12)
    # Alternating elliptical chain links, combined as one mesh.
    verts, faces = [], []
    for i in range(20):
        for k in range(12):
            angle = math.tau * k / 12
            center = Vector((-23.8 + (.045 * math.cos(angle) if i % 2 else 0),
                             -2.7 + (.045 * math.cos(angle) if not i % 2 else 0),
                             2.24 - i * .065 + .06 * math.sin(angle)))
            for j in range(4):
                phi = math.tau * j / 4
                verts.append(tuple(center + Vector((.009 * math.cos(phi), .009 * math.sin(phi), 0))))
        base = i * 48
        for k in range(12):
            for j in range(4):
                faces.append((base + k * 4 + j, base + ((k + 1) % 12) * 4 + j,
                              base + ((k + 1) % 12) * 4 + (j + 1) % 4, base + k * 4 + (j + 1) % 4))
    t.obj("prison_bell_chain", t.mesh("chain_links", verts, faces, "iron"))
    t.location("kennel")
    t.box("kennel_yard", (-12, 6, .01), (7, 8, .1), "dirt_road")
    for x in (-15.5, -8.5):
        t.box("kennel_yard_wall", (x, 6, .85), (.4, 8, 1.7), "rubble_stone")
    for x in (-12.7, -11.3):
        t.box("kennel_side", (x, 7, .5), (.12, 1.6, 1), "wood_planks")
    t.box("kennel_back", (-12, 7.8, .5), (1.5, .12, 1), "wood_planks")
    t.box("kennel_front_top", (-12, 6.2, .95), (1.5, .12, .16), "wood_planks")
    t.roof("kennel", -12, 7, 1.6, 1.8, 1)
    t.box("kennel_dog_silhouette", (-12, 7.1, .4), (.55, .7, .65), "cloth_wool", .15)
    for x in (-12.12, -11.88):
        eye = t.box("kennel_eye", (x, 6.73, .55), (.045, .025, .045), "glass", .01)
        eye["glint_target"] = True


def _civic(t):
    t.location("cathedral")
    t.house("cathedral_nave", 0, 24, 16, 28, 4)
    t.box("cathedral_clock_tower", (8, 22, 17.5), (7.5, 8, 35), "limestone_wall", .06)
    for z in (9, 21, 31, 35):
        t.box("tower_cornice", (8, 22, z), (8.1, 8.6, .35), "limestone_wall")
    for x in (-8.5, 8.5):
        for y in (14, 22, 30, 36):
            t.box("cathedral_buttress", (x, y, 4), (1.3, 1.4, 8), "limestone_wall")
    for x in (6, 8, 10):
        t.box("belfry_recess", (x, 17.94, 32.5), (1, .06, 2.2), "wood_planks")
        for z in (31.7, 32.1, 32.5, 32.9, 33.3):
            t.box("belfry_louver", (x, 17.83, z), (1.05, .18, .12), "wood_planks")
    t.rod("clock_face", (8, 17.85, 28), (8, 17.72, 28), 1.5, "plaster", 64)
    for i in range(12):
        angle = i * math.tau / 12
        tick = t.box("clock_hour_mark", (8 + 1.23 * math.sin(angle), 17.62, 28 + 1.23 * math.cos(angle)), (.08, .04, .24), "iron")
        tick.rotation_euler.y = angle
    t.rod("clock_minute_hand", (8, 17.55, 28), (8, 17.55, 29.12), .045)
    t.rod("clock_hour_hand", (8, 17.52, 28), (8.7, 17.52, 28.4), .065)
    t.location("hospital")
    t.house("hospital_old_palace", 90, 0, 27, 16, 3)
    # A low west wing physically adjoins the bishop's east wall, while leaving
    # his south guest window clear. The palace centre remains exactly (90, 0).
    t.house("hospital_west_wing", 71.25, 2, 10.5, 6, 2)
    t.box("hospital_garden", (90, 18, -.01), (27, 18, .1), "forest_floor")
    for x in (77, 103):
        t.box("hospital_garden_wall", (x, 18, 1), (.45, 18, 2), "rubble_stone")
    t.box("hospital_rear_wall", (90, 27, 1), (27, .45, 2), "rubble_stone")


def _bishop(t):
    t.location("bishop_house")
    # Full envelope with actual door/window openings; interior cameras stay below ceiling.
    # Explicit ground-front panels keep the canonical street door at x=57.
    for cx, width in ((55.2, 2.4), (61.8, 8.4)):
        t.box("bishop_front_wall", (cx, -9, 1.4), (width, .4, 2.8))
    t.box("bishop_door_lintel", (57, -9, 2.48), (1.2, .4, .64))
    t.door("bishop_street_door", 57, -9)
    t.facade("bishop_upper_front", 60, -9, 12, 2.8, floors=1)
    # Move upper storey facade objects as a group.
    for obj in list(t.col.objects):
        if obj.name.startswith("bishop_upper_front"):
            obj.location.z += 2.8
    # Garden door at x=57 and bedroom window at canonical x=63.
    for cx, width in ((55.2, 2.4), (59.95, 4.7), (64.85, 2.3)):
        t.box("bishop_north_wall", (cx, 1, 1.4), (width, .4, 2.8))
    t.box("bishop_garden_door_lintel", (57, 1, 2.48), (1.2, .4, .64))
    t.door("bishop_garden_door", 57, 1, north=True)
    for z, h in ((.5, 1), (2.65, .3)):
        t.box("bedroom_window_surround", (63, 1, z), (1.4, .4, h))
    t.box("bedroom_window_glass", (63, 1.12, 1.75), (1.4, .025, 1.5), "glass")
    t.box("bedroom_window_mullion", (63, 1, 1.75), (.07, .1, 1.5), "wood_planks")
    t.box("bedroom_window_sill", (63, 1, 1), (1.6, .65, .12), "limestone_wall")
    for x in (62, 64):
        t.box("bedroom_garden_shutter", (x, 1.25, 1.75), (.5, .08, 1.5), "wood_planks")
    t.box("bishop_north_upper", (60, 1, 4.2), (12, .4, 2.8))
    t.box("bishop_west_wall", (54, -4, 2.8), (.4, 10, 5.6))
    # East wall has an actual guest-alcove moon window.
    for cy, depth in ((-7.8, 2.4), (-2.2, 6.4)):
        t.box("bishop_east_wall", (66, cy, 2.8), (.4, depth, 5.6))
    for z, h in ((.5, 1), (4, 3.2)):
        t.box("guest_window_surround", (66, -6, z), (.4, 1.2, h))
    t.box("guest_window_glass", (66.12, -6, 1.7), (.025, 1.2, 1.4), "glass")
    t.box("bishop_first_floor", (60, -4, 2.95), (12, 10, .22), "wood_planks")
    t.roof("bishop_house", 60, -4, 12, 10, 5.6)
    t.box("bishop_chimney", (54.7, -2, 6), (.85, 1.1, 3), "limestone_wall")
    t.location("dining_room")
    t.box("dining_floor", (57, -4, -.06), (6, 10, .12), "wood_planks")
    # Doorway through the bedroom partition, open passage into the guest alcove.
    for cy, depth in ((-7, 4), (0, 2)):
        t.box("bedroom_partition", (60, cy, 1.4), (.18, depth, 2.8))
    t.box("bedroom_passage_lintel", (60, -3, 2.5), (.18, 2, .6))
    for y in (-2.85, -1.15):
        t.box("fireplace_jamb", (54.65, y, .7), (.7, .3, 1.4), "limestone_wall", .03)
    t.box("fireplace_mantel", (54.7, -2, 1.45), (.95, 2.25, .22), "limestone_wall", .03)
    t.box("fireplace_hearth", (54.8, -2, .06), (1.5, 2.2, .12), "limestone_wall")
    for y in (-2.3, -1.8):
        t.rod("fireplace_log", (54.4, y, .2), (55, y + .2, .25), .12, "wood_planks")
    t.light("fireplace", (54.9, -2, .5), 95, (1, .28, .06), .35)
    if not t.prop("table", "dining_table", (57, -3.8, .4), (2, 3, .8)):
        t.box("dining_table_top", (57, -3.8, .75), (2, 3, .12), "wood_planks", .025)
        for x in (56.2, 57.8):
            for y in (-5, -2.6):
                t.box("dining_table_leg", (x, y, .35), (.12, .12, .7), "wood_planks")
    for x in (55.7, 58.3):
        if not t.prop("chair", "dining_chair", (x, -3.8, .5), (.65, .65, 1)):
            t.box("chair_seat", (x, -3.8, .45), (.65, .65, .1), "wood_planks")
            t.box("chair_back", (x + (-.28 if x < 57 else .28), -3.8, .9), (.08, .65, .85), "wood_planks")
            for dx in (-.24, .24):
                for dy in (-.24, .24):
                    t.box("chair_leg", (x + dx, -3.8 + dy, .22), (.07, .07, .44), "wood_planks")
    t.location("bishop_bedroom")
    t.box("bedroom_floor", (63, -1, -.06), (6, 4, .12), "wood_planks")
    # Separating wall has a 1.2m opening to guest room.
    for x, w in ((60.6, 1.2), (64.2, 3.6)):
        t.box("guest_partition", (x, -3, 1.4), (w, .18, 2.8))
    t.box("guest_partition_lintel", (61.8, -3, 2.5), (1.2, .18, .6))
    t.bed("bishop_bed", 63.7, -1.2)
    # Cupboard carcass remains hollow so silver is visible when hinged door opens.
    for y in (-1.55, -.05):
        t.box("silver_cupboard_side", (60.6, y, 1), (.8, .1, 2), "wood_planks")
    t.box("silver_cupboard_back", (60.25, -.8, 1), (.1, 1.6, 2), "wood_planks")
    for z in (.12, 1.12, 2):
        t.box("silver_cupboard_shelf", (60.6, -.8, z), (.8, 1.6, .08), "wood_planks")
    door = t.box("silver_cupboard_door", (61.03, -.8, 1), (.08, 1.6, 2), "wood_planks", .02)
    door.data = door.data.copy()
    for v in door.data.vertices:
        v.co.y += .8
        v.co.z += 1
    door.location = (61.03, -1.6, 0)
    t.location("guest_alcove")
    t.box("guest_floor", (63, -6, -.06), (6, 6, .12), "wood_planks")
    t.bed("guest_bed", 64, -6)
    t.location("garden")
    t.box("garden_soil", (60, 10, -.02), (12, 18, .12), "forest_floor")
    t.box("garden_path", (60, 10, .05), (1.5, 18, .1), "dirt_road")
    for x in (54, 66):
        t.box("garden_side_wall", (x, 10, 1.1), (.45, 18, 2.2), "rubble_stone")
    t.box("garden_vault_wall", (60, 19, 1.1), (12, .45, 2.2), "rubble_stone")
    t.box("garden_wall_coping", (60, 19, 2.2), (12.2, .6, .12), "limestone_wall", .04)
    for x in (56.3, 63.2):
        for y in (5, 10, 14.5):
            t.box("flower_bed", (x, y, .12), (3, 2.5, .2), "forest_floor")
            for j in range(4):
                xx, yy = x + (j % 2 - .5), y + (j // 2 - .5)
                if not t.prop("shrub", "garden_shrub", (xx, yy, .45), (.7, .7, .65), "dry_grass"):
                    t.rod("garden_shrub", (xx, yy, .15), (xx, yy, .7), .28, "dry_grass", 7)
                for k in range(3):
                    t.box("flower_head", (xx + .12 * k, yy, .75 + .04 * k), (.09, .09, .06), "plaster", .02)


def _memories(t):
    t.location("bakery_flashback")
    t.house("bakery", -240, 90, 8, 8, 2)
    # Hero bakery window overrides the central door bay, leaving the aperture open.
    generic = bpy.data.objects.get("bakery_door")
    if generic:
        for child in list(generic.children):
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(generic, do_unlink=True)
    t.box("bakery_window_counter", (-240, 86, 1.12), (1.3, .8, .16), "wood_planks")
    for x in (-240.4, -240, -239.6):
        pane = t.box("bakery_breakable_pane", (x, 85.96, 1.65), (.38, .025, .88), "glass")
        pane["breakable"] = True
    t.box("bakery_street", (-240, 83, -.04), (14, 7, .1), "cobblestone")
    t.light("bakery_oven_glow", (-239, 87.5, 1.7), 90, (1, .43, .15), 1, (-240, 85, 1.2))
    t.memory_grade()
    t.location("galley_flashback")
    t.box("galley_floor", (-240, 125, -.1), (8, 8, .2), "limestone_wall")
    for x in (-244, -236):
        t.box("galley_side_wall", (x, 125, 1.8), (.5, 8, 3.6), "rubble_stone")
    # Back wall surrounds a genuine barred shaft-light opening.
    for x in (-242.5, -237.5):
        t.box("galley_back_pier", (x, 129, 1.8), (3, .5, 3.6), "limestone_wall")
    for z, height in ((1, 2), (3.4, .4)):
        t.box("galley_back_spandrel", (-240, 129, z), (2, .5, height), "limestone_wall")
    for x in (-240.8, -240.4, -240, -239.6, -239.2):
        t.rod("galley_window_bar", (x, 129, 2), (x, 129, 3.2), .035)
    t.box("galley_ceiling", (-240, 125, 3.7), (8, 8, .2), "limestone_wall")
    for group in range(4):
        for i in range(4):
            y = 124.2 + group * .5 + i * .075
            t.rod("galley_tally", (-243.73, y, 1.2), (-243.73, y + .03, 1.6), .009, "forest_floor", 4)
        t.rod("galley_tally_cross", (-243.72, 124.17 + group * .5, 1.27), (-243.72, 124.52 + group * .5, 1.53), .009, "forest_floor", 4)
    t.light("galley_window_shaft", (-240, 130, 3), 220, (.5, .65, 1), .6, (-242, 123, .5))
    t.memory_grade()


def build(ctx):
    """Build on a fresh factory scene; return location collections for callers."""
    print("[world] Building Digne: 1 unit = 1 metre; Blender", bpy.app.version_string)
    if bpy.app.version < (4, 2, 0):
        raise RuntimeError("[world] Blender 4.2 LTS or newer required")
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1
    t = Town(ctx)
    _landscape(t)
    _street(t)
    _civic(t)
    _bishop(t)
    _memories(t)
    cameras = ctx.col("CAMERAS")
    for name, spec in LOOKDEV_CAMERAS.items():
        data = bpy.data.cameras.new("LOOKDEV_" + name)
        obj = bpy.data.objects.new(data.name, data)
        cameras.objects.link(obj)
        obj.location = spec["loc"]
        lib.look_at(obj, spec["target"])
        data.lens = spec["lens_mm"]
        data.clip_end = 1500
        data.dof.use_dof = True
        data.dof.focus_distance = (Vector(spec["target"]) - obj.location).length
        data.dof.aperture_fstop = 8
        obj["time_of_day"] = spec["time"]
    lib.set_time_of_day(ctx, bpy.context.scene, "dusk")
    bpy.context.scene.camera = bpy.data.objects["LOOKDEV_road"]
    print("[world] Built", len(LOCATIONS), "places and", len(LOOKDEV_CAMERAS), "lookdev cameras")
    return {name: ctx.col(name) for name in LOCATIONS}
