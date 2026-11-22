"""Blender (arka planda, ekransız) ile 3D modeli N yönden şeffaf arka planlı sprite olarak çizer.
Kullanım: blender -b --python uc_boyut/blender_yonler.py -- model.ply cikis_klasoru yon_sayisi boyut [rx ry rz on_aci]
rx/ry/rz: modeli dik ve öne bakar hale getiren dönüş (derece); on_aci: ön yüzün açısı.
Ayrıca 'eksen_*.png' teşhis görüntüleri (6 eksenden) üretir — doğru dönüşü bulmak için."""
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
model, cikis, yon, boyut = argv[0], argv[1], int(argv[2]), int(argv[3])
rx, ry, rz, on_aci = (float(x) for x in (argv[4:8] if len(argv) >= 8 else (0, 0, 0, 0)))
os.makedirs(cikis, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
if model.endswith(".ply"):
    bpy.ops.wm.ply_import(filepath=model)
else:
    bpy.ops.import_scene.gltf(filepath=model)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]

# köşe renklerini kullanan mat malzeme
for o in objs:
    me = o.data
    mat = bpy.data.materials.new("renk")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    if me.color_attributes:
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = me.color_attributes[0].name
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    me.materials.clear()
    me.materials.append(mat)

# modeli merkeze al, dik çevir
pivot = bpy.data.objects.new("pivot", None)
bpy.context.scene.collection.objects.link(pivot)
for o in objs:
    o.parent = pivot
pivot.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
merkez = (mn + mx) / 2
dis = bpy.data.objects.new("dis", None)  # dönüş ekseni: modelin merkezi
bpy.context.scene.collection.objects.link(dis)
pivot.parent = dis
pivot.location = -merkez
olcek = max(mx - mn)

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 24
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = boyut
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("dunya")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
sc.world = w

cam = bpy.data.objects.new("kamera", bpy.data.cameras.new("kamera"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = olcek * 1.15
sc.collection.objects.link(cam)
sc.camera = cam
gunes = bpy.data.objects.new("gunes", bpy.data.lights.new("gunes", "SUN"))
gunes.data.energy = 2.5
sc.collection.objects.link(gunes)


def bak(yonu, ust=(0, 0, 1)):
    """Kamerayı 'yonu' tarafına koyup merkeze baktır."""
    v = Vector(yonu).normalized() * olcek * 3
    cam.location = v
    cam.rotation_euler = (-v).to_track_quat("-Z", "Y").to_euler()
    gunes.location = v
    gunes.rotation_euler = cam.rotation_euler


def ciz(yol):
    sc.render.filepath = yol
    bpy.ops.render.render(write_still=True)


# teşhis: 6 eksenden
for ad, v in {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0.0001, 1), "-z": (0, 0.0001, -1)}.items():
    dis.rotation_euler = (0, 0, 0)
    bak(v)
    ciz(f"{cikis}/eksen_{ad}.png")

# yönler: kamera önde (-Y), model kendi ekseninde döner; 0 = ön
bak((0, -1, 0.15))
for k in range(yon):
    aci = on_aci + k * 360.0 / yon
    dis.rotation_euler = (0, 0, math.radians(aci))
    ciz(f"{cikis}/yon_{k:02d}_{int(k * 360 / yon):03d}.png")
print("bitti", flush=True)
