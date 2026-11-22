"""Blender (ekransız): 3D modele otomatik insan iskeleti takar, yürüme/koşma döngüsünü 8 yönden kare kare çizer.
Kullanım: blender -b --python uc_boyut/blender_anim.py -- model.ply cikis yon kare boyut on_aci egim animasyonlar
  on_aci: modelin ön yüzünü kameraya çeviren açı (TripoSR için 270), egim: kamera yükseklik açısı (Commandos ~35)
  animasyonlar: virgüllü, ör. "yuru,kos"
İskelet: modelin boyu ve bacak/kol konumları kesitlerden ölçülür; ağırlıklar kemik parçalarına uzaklıkla verilir
(sol/sağ ayrımı korunur — sol bacağın köşesi sağ bacağa bağlanmaz)."""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
model, cikis = argv[0], argv[1]
yon, kare, boyut = int(argv[2]), int(argv[3]), int(argv[4])
on_aci, egim = float(argv[5]), float(argv[6])
animler = argv[7].split(",")
os.makedirs(cikis, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.ply_import(filepath=model)
ob = [o for o in bpy.context.scene.objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
# ön yüz -Y'ye (Blender önü) bakacak şekilde döndür, dönüşü uygula
ob.rotation_euler = (0, 0, math.radians(on_aci + 90))
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

me = ob.data
mat = bpy.data.materials.new("renk")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.9
if me.color_attributes:
    vc = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = me.color_attributes[0].name
    mat.node_tree.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
me.materials.clear()
me.materials.append(mat)

V = np.array([v.co[:] for v in me.vertices])
zmin, zmax = V[:, 2].min(), V[:, 2].max()
H = zmax - zmin
V[:, 2] -= zmin  # ayak tabanı z=0
V[:, 0] -= np.median(V[:, 0])  # dönüş ekseni karakterin ortası olsun
V[:, 1] -= np.median(V[:, 1])
for v, c in zip(me.vertices, V):
    v.co = Vector(c)
cx, cy = 0.0, 0.0


def kesit(a, b):
    m = (V[:, 2] > a * H) & (V[:, 2] < b * H)
    return V[m]


# bacaklar: diz hizasında sol/sağ küme merkezleri
d = kesit(0.18, 0.32)
lx = float(d[d[:, 0] < cx][:, 0].mean()) if (d[:, 0] < cx).any() else cx - 0.08 * H
rx = float(d[d[:, 0] >= cx][:, 0].mean()) if (d[:, 0] >= cx).any() else cx + 0.08 * H
# kollar: bel hizasında en dıştaki noktalar (kollar genelde yanlarda)
k = kesit(0.50, 0.66)
kol_l = float(np.percentile(k[:, 0], 4)) if len(k) else cx - 0.2 * H
kol_r = float(np.percentile(k[:, 0], 96)) if len(k) else cx + 0.2 * H
omuz_l, omuz_r = cx + (kol_l - cx) * 0.8, cx + (kol_r - cx) * 0.8
print(f"boy {H:.3f} · bacak x {lx:.3f}/{rx:.3f} · kol x {kol_l:.3f}/{kol_r:.3f}", flush=True)

# iskelet (Blender'da karakterin solu = +X değil: kameraya bakan karakterin sağı ekranın solunda; adlar bu yüzden L=-X)
arm = bpy.data.armatures.new("iskelet")
ao = bpy.data.objects.new("iskelet", arm)
bpy.context.scene.collection.objects.link(ao)
bpy.context.view_layer.objects.active = ao
bpy.ops.object.mode_set(mode="EDIT")
K = {}


def kemik(ad, bas, uc, ebeveyn=None):
    b = arm.edit_bones.new(ad)
    b.head, b.tail = Vector(bas), Vector(uc)
    b.roll = 0
    if ebeveyn:
        b.parent = arm.edit_bones[ebeveyn]
    K[ad] = (np.array(bas), np.array(uc))


kemik("kalca", (cx, cy, 0.50 * H), (cx, cy, 0.62 * H))
kemik("govde", (cx, cy, 0.62 * H), (cx, cy, 0.80 * H), "kalca")
kemik("bas", (cx, cy, 0.80 * H), (cx, cy, 1.0 * H), "govde")
for t, x, ox, kx in (("L", lx, omuz_l, kol_l), ("R", rx, omuz_r, kol_r)):
    kemik(f"uyluk.{t}", (x, cy, 0.50 * H), (x, cy, 0.27 * H), "kalca")
    kemik(f"baldir.{t}", (x, cy, 0.27 * H), (x, cy, 0.03 * H), f"uyluk.{t}")
    kemik(f"pazu.{t}", (ox, cy, 0.79 * H), (kx, cy, 0.62 * H), "govde")
    kemik(f"onkol.{t}", (kx, cy, 0.62 * H), (kx, cy, 0.45 * H), f"pazu.{t}")
bpy.ops.object.mode_set(mode="OBJECT")


# ağırlıklar: kemik parçasına uzaklık (yumuşak), sol/sağ ayrımı
def parca_uzaklik(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(1e-9, ab @ ab), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


adlar = list(K)
D = np.stack([parca_uzaklik(V, *K[a]) for a in adlar], 1)
sol = V[:, 0] < cx
for j, a in enumerate(adlar):
    if a.endswith(".L"):
        D[~sol & (V[:, 2] < 0.5 * H), j] = 1e9  # alt gövdede karşı taraf bacağa bağlanmasın
        if a.startswith(("pazu", "onkol")):
            D[~sol, j] = 1e9
    if a.endswith(".R"):
        D[sol & (V[:, 2] < 0.5 * H), j] = 1e9
        if a.startswith(("pazu", "onkol")):
            D[sol, j] = 1e9
sig = 0.035 * H
W = np.exp(-((D - D.min(1, keepdims=True)) / sig) ** 2)
W[D > 1e8] = 0
W /= W.sum(1, keepdims=True)
for j, a in enumerate(adlar):
    g = ob.vertex_groups.new(name=a)
    for i in np.nonzero(W[:, j] > 0.02)[0]:
        g.add([int(i)], float(W[i, j]), "REPLACE")
mod = ob.modifiers.new("iskelet", "ARMATURE")
mod.object = ao
ob.parent = ao

# sahne, ışık, kamera (Commandos açısı: yukarıdan 'egim' derece)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 12
sc.render.film_transparent = True
sc.render.resolution_x = sc.render.resolution_y = boyut
sc.view_settings.view_transform = "Standard"
w = bpy.data.worlds.new("dunya")
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.2
sc.world = w
cam = bpy.data.objects.new("kamera", bpy.data.cameras.new("kamera"))
cam.data.type = "ORTHO"
cam.data.ortho_scale = H * 1.35
sc.collection.objects.link(cam)
sc.camera = cam
e = math.radians(egim)
hedef = Vector((cx, cy, 0.5 * H))
v = Vector((0, -math.cos(e), math.sin(e))) * H * 4
cam.location = hedef + v
cam.rotation_euler = (-v).to_track_quat("-Z", "Y").to_euler()
gunes = bpy.data.objects.new("gunes", bpy.data.lights.new("gunes", "SUN"))
gunes.data.energy = 3.0
gunes.rotation_euler = (math.radians(40), 0, math.radians(-30))
sc.collection.objects.link(gunes)

# hareket tanımları: faz p (0..2π) → kemik açıları (derece, yerel X etrafında; + = geriye)
ANIM = {
    "yuru": dict(uyluk=26, diz=40, kol=22, onkol=12, zip_=0.012, egil=4),
    "kos": dict(uyluk=42, diz=75, kol=40, onkol=45, zip_=0.03, egil=12),
}
pb = ao.pose.bones
for b in pb:
    b.rotation_mode = "XYZ"


def poz(ad, p):
    A = ANIM[ad]
    s, c = math.sin(p), math.cos(p)
    for t, isaret in (("L", 1), ("R", -1)):
        sp, cp = isaret * s, isaret * c
        pb[f"uyluk.{t}"].rotation_euler = (math.radians(-A["uyluk"] * sp), 0, 0)
        # diz: bacak öne savrulurken (salınım) bükülür, ayak yerdeyken düz
        pb[f"baldir.{t}"].rotation_euler = (math.radians(A["diz"] * max(0.0, -cp) + 5), 0, 0)
        pb[f"pazu.{t}"].rotation_euler = (math.radians(A["kol"] * sp), 0, 0)
        pb[f"onkol.{t}"].rotation_euler = (math.radians(-A["onkol"]), 0, 0)
    pb["govde"].rotation_euler = (math.radians(-A["egil"]), 0, 0)
    pb["kalca"].location = (0, A["zip_"] * H * abs(math.sin(p)), 0)  # kemiğin Y'si yukarı: adımda hafif zıplama


for ad in animler:
    if ad not in ANIM:
        continue
    for yk in range(yon):
        ao.rotation_euler = (0, 0, math.radians(yk * 360.0 / yon))
        for f in range(kare):
            poz(ad, 2 * math.pi * f / kare)
            bpy.context.view_layer.update()
            sc.render.filepath = f"{cikis}/{ad}_y{yk}_k{f}.png"
            bpy.ops.render.render(write_still=True)
        print(f"{ad} yön {yk} bitti", flush=True)
print("bitti", flush=True)
