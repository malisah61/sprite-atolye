"""Komando hattı (Blender, ekransız): atölyede üretilen karakterin 3D modelini (TripoSR) Quaternius UAL (CC0)
iskeletine oturtur, Komando'nun kendi sahnesi/kamerasıyla 8 yönlü, 8 animasyonlu sprite sayfası çıkarır.
Çıktı Komando'nun mevcut sayfalarıyla AYNI düzende (128 px kare, slot düzeni, json) → oyunda değişiklik gerekmez.

Kullanım (Komando reposu KOMANDO_DIR klasöründe olmalı):
  blender -b --python siparis/komando_hatti.py -- model.ply cikis_klasoru ad [ekipman,virgullu] [--quick]
  ekipman: rifle, webbing, canteen, knife, belt (Komando asker.py ile aynı adlar) + başlık: helmet / beret / cap

Adımlar:
 1) Komando sahnesi (asker.setup_scene: 50° kamera, ortho 4.2, güneş, gölge yakalayıcı zemin)
 2) UAL mankeni + iskelet (asker2.load_ual) — hareketler hazır (motion capture)
 3) Model: ön yüz -Y, boy mankene eşitlenir, kollar mankenin T-poz kollarına hizalanır (kol boyu/yüksekliği)
 4) Ağırlıklar mankenden en yakın yüzey ile aktarılır (Data Transfer); sol/sağ bacak arası gerilen yüzler kesilir
 5) Manken gizlenir, model iskelete bağlanır, asker2 ile aynı döngüyle render alınır.
"""
import json
import math
import os
import sys
import tempfile

import bmesh
import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
MODEL = os.path.abspath(argv[0])
OUT = os.path.abspath(argv[1])
AD = argv[2]
EKIPMAN = [e for e in (argv[3].split(",") if len(argv) > 3 and not argv[3].startswith("--") else []) if e]
QUICK = "--quick" in argv
ON_ACI = 270.0  # TripoSR: ön yüz +X → 270° ile -Y (Blender önü)

KOMANDO = os.path.abspath(os.environ.get("KOMANDO_DIR", "komando"))
sys.path.insert(0, os.path.join(KOMANDO, "tools", "blender"))
os.chdir(KOMANDO)  # asker2 UAL dosyasını göreli yoldan açar
import asker as A  # noqa: E402
import asker2 as U  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
A._materials.clear()
A.setup_scene()
sc = bpy.context.scene
if QUICK:
    sc.cycles.samples = 8

# ---------------------------------------------------------------- manken + iskelet
rig, body = U.load_ual()
rig.animation_data_create()
rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.location = (0, 0, 0)
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
be = body.evaluated_get(dg)
MW = np.array([(be.matrix_world @ v.co)[:] for v in be.data.vertices])
MH = MW[:, 2].max() - MW[:, 2].min()
M0 = MW[:, 2].min()
ust = MW[MW[:, 2] > M0 + 0.6 * MH]
m_uzan = float(np.percentile(np.abs(ust[:, 0]), 99.5))
m_kol = MW[np.abs(MW[:, 0]) > 0.6 * m_uzan]
m_kol_z = float(np.median(m_kol[:, 2]))
sh_m = abs((rig.matrix_world @ rig.pose.bones["DEF-upper_arm.L"].head).x)
print(f"manken boy {MH:.2f} uzanım {m_uzan:.2f} kol z {m_kol_z:.2f} omuz x {sh_m:.2f}", flush=True)

# ---------------------------------------------------------------- model
onceki = set(bpy.data.objects)
bpy.ops.wm.ply_import(filepath=MODEL)
ob = [o for o in bpy.data.objects if o not in onceki and o.type == "MESH"][0]
ob.name = "karakter"
for o in bpy.context.selected_objects:
    o.select_set(False)
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
ob.rotation_euler = (0, 0, math.radians(ON_ACI))
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
# fazla yoğun ağ → ~14 bin yüz (ağırlık aktarımı ve render hızı)
nf = len(ob.data.polygons)
if nf > 16000:
    d = ob.modifiers.new("azalt", "DECIMATE")
    d.ratio = 14000 / nf
    bpy.ops.object.modifier_apply(modifier="azalt")

me = ob.data
V = np.array([v.co[:] for v in me.vertices])
z0, z1 = V[:, 2].min(), V[:, 2].max()
H = z1 - z0
govde = V[(V[:, 2] > z0 + 0.35 * H) & (V[:, 2] < z0 + 0.7 * H)]
cx = float(np.median(govde[:, 0]))
cy = float(np.median(govde[:, 1]))
s = MH / H
V[:, 0] = (V[:, 0] - cx) * s
V[:, 1] = (V[:, 1] - cy) * s
V[:, 2] = (V[:, 2] - z0) * s + M0
H = MH
for v, c in zip(me.vertices, V):
    v.co = Vector(c)
me.update()

# kollar: görsel modeli çoğu zaman kollar aşağıda çiziyor. T-pozdaysa kol boyu/yüksekliği mankene hizalanır;
# değilse mankenin kolları modele en iyi oturan açıya indirilir, ağırlıklar o pozdan aktarılır ve model
# ters dönüşle T-poza açılır (hareketler T-poz dinlenme pozuna göre yazılmış).
ust = V[V[:, 2] > M0 + 0.55 * H]
uzan = float(np.percentile(np.abs(ust[:, 0]), 99.7))
KOL_ACI = 0.0
KOLLAR = [b for b in rig.pose.bones if b.name in ("DEF-upper_arm.L", "DEF-upper_arm.R")]


def kol_poz(aci):
    for pb in KOLLAR:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for pb in KOLLAR:
        hw = rig.matrix_world @ pb.head
        isaret = 1.0 if hw.x > 0 else -1.0
        Rw = Matrix.Translation(hw) @ Matrix.Rotation(math.radians(isaret * aci), 4, "Y") @ Matrix.Translation(-hw)
        pb.matrix = rig.matrix_world.inverted() @ Rw @ rig.matrix_world @ pb.matrix
        bpy.context.view_layer.update()


if uzan > 0.75 * m_uzan:
    kol = V[(np.abs(V[:, 0]) > 0.6 * uzan) & (V[:, 2] > M0 + 0.5 * H)]
    kol_z = float(np.median(kol[:, 2]))
    k = float(np.clip((m_uzan - sh_m) / max(1e-6, uzan - sh_m), 0.8, 1.25))
    dz = m_kol_z - kol_z
    ax = np.abs(V[:, 0])
    t = np.clip((ax - 0.8 * sh_m) / (0.6 * sh_m), 0, 1)
    t = t * t * (3 - 2 * t)
    t *= np.clip((V[:, 2] - (M0 + 0.42 * H)) / (0.08 * H), 0, 1)
    hedef = sh_m + (ax - sh_m) * k
    V[:, 0] = np.sign(V[:, 0]) * (ax + t * (hedef - ax))
    V[:, 2] += t * dz
    for v, c in zip(me.vertices, V):
        v.co = Vector(c)
    me.update()
    print(f"T-poz: kollar hizalandı (k={k:.2f}, yükseklik {kol_z:.2f}→{m_kol_z:.2f})", flush=True)
else:
    from mathutils.kdtree import KDTree
    rng = np.random.default_rng(0)
    ornek = V[rng.choice(len(V), min(4000, len(V)), replace=False)]
    sonuc = []
    for aci in (40, 50, 58, 66, 74, 82):
        kol_poz(aci)
        dg = bpy.context.evaluated_depsgraph_get()
        be = body.evaluated_get(dg)
        P = [be.matrix_world @ v.co for v in be.data.vertices]
        kd = KDTree(len(P))
        for i, q in enumerate(P):
            kd.insert(q, i)
        kd.balance()
        mesafe = float(np.mean([kd.find(Vector(q))[2] for q in ornek]))
        sonuc.append((mesafe, aci))
    KOL_ACI = min(sonuc)[1]
    kol_poz(KOL_ACI)
    print(f"kollar aşağıda (uzanım {uzan:.2f}): manken kolları {KOL_ACI}° indirildi · uyum {[(a, round(m, 3)) for m, a in sonuc]}", flush=True)

# ---------------------------------------------------------------- ağırlık aktarımı (mankenden)
dt = ob.modifiers.new("aktar", "DATA_TRANSFER")
dt.object = body
dt.use_vert_data = True
dt.data_types_verts = {"VGROUP_WEIGHTS"}
dt.vert_mapping = "POLYINTERP_NEAREST"
dt.layers_vgroup_select_src = "ALL"
dt.layers_vgroup_select_dst = "NAME"
bpy.context.view_layer.objects.active = ob
bpy.ops.object.datalayout_transfer(modifier="aktar")
bpy.ops.object.modifier_apply(modifier="aktar")
print(f"ağırlık grupları: {len(ob.vertex_groups)}", flush=True)

# sol/sağ bacak arasında gerilen yüzleri kes (bacaklar modelde yapışık olabilir)
gad = {g.index: g.name for g in ob.vertex_groups}


def taraf(v):
    en, ad = 0.0, ""
    for g in v.groups:
        if g.weight > en:
            en, ad = g.weight, gad[g.group]
    t = "L" if ad.endswith(".L") else "R"
    if any(x in ad for x in ("thigh", "shin", "foot", "toe")):
        return "bacak" + t
    if any(x in ad for x in ("upper_arm", "forearm", "hand", "f_", "thumb", "palm")):
        return "kol" + t
    return "govde"


T = [taraf(v) for v in me.vertices]
bm = bmesh.new()
bm.from_mesh(me)
sil = []
for f in bm.faces:
    gs = {T[v.index] for v in f.verts}
    if {"bacakL", "bacakR"} <= gs:
        sil.append(f)
    elif KOL_ACI and "govde" in gs and ({"kolL", "kolR"} & gs):
        sil.append(f)   # gövdeye yapışık çizilen kol açılınca aradaki yüzler perde gibi gerilmesin
bmesh.ops.delete(bm, geom=sil, context="FACES_ONLY")
bm.to_mesh(me)
bm.free()
print(f"uzuvlar arası kesilen yüz: {len(sil)}", flush=True)

# kollar aşağıdaysa: modeli T-poza aç (mankenin indirilmiş kollarının ters dönüşü, ağırlıklarla)
if KOL_ACI:
    kol_poz(-KOL_ACI)   # dinlenme pozuna göre ters açı: aşağıdaki kol T-poza kalkar
    ac = ob.modifiers.new("ac", "ARMATURE")
    ac.object = rig
    # model henüz iskeletin çocuğu değil: dünya koordinatında aynı yerde, iskelet nesnesi dönüşü hesaba katılır
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier="ac")
    for pb in KOLLAR:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    print("model T-poza açıldı", flush=True)

# malzeme: TripoSR köşe renkleri
mat = bpy.data.materials.new("karakter_renk")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.85
if me.color_attributes:
    vc = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = me.color_attributes[0].name
    mat.node_tree.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
me.materials.clear()
me.materials.append(mat)
for p in me.polygons:
    p.use_smooth = True

# mankeni gizle, modeli iskelete bağla
body.hide_render = True
body.hide_viewport = True
ob.parent = rig
ob.matrix_parent_inverse = rig.matrix_world.inverted()
am = ob.modifiers.new("iskelet", "ARMATURE")
am.object = rig

# ekipman (asker2.add_gear ile aynı parçalar)
bas = "none"
for b, ad in (("helmet", "stahlhelm"), ("beret", "beret"), ("cap", "cap")):
    if b in EKIPMAN:
        bas = ad
o = {"head": bas, "head_color": (0.34, 0.37, 0.31), "gear": (0.30, 0.24, 0.16),
     "items": [e for e in EKIPMAN if e in ("rifle", "webbing", "canteen", "knife", "belt")]}
if o["items"] or bas != "none":
    U.add_gear(rig, o)

# ---------------------------------------------------------------- render (asker2.render_outfit ile aynı düzen)
anims = U.ANIMS if not QUICK else [a for a in U.ANIMS if a[0] in ("idle", "walk", "death")]
n_slots = len(anims) * A.DIRS
rows = (n_slots + A.SLOTS_PER_ROW - 1) // A.SLOTS_PER_ROW
cols = A.SLOT * A.SLOTS_PER_ROW
F = A.FRAME
sheet = np.zeros((rows * F, cols * F, 4), dtype=np.float32)
tmp_png = os.path.join(tempfile.mkdtemp(), "f.png")
layout = {"frame": F, "cols": cols, "slot": A.SLOT, "slots_per_row": A.SLOTS_PER_ROW,
          "directions": A.DIRS, "filter": "linear", "display_px": 160, "anims": {},
          "kaynak": "Sprite Atölye (görsel → TripoSR → UAL)"}
slot = 0
for anim, act_name, n, fps, loop in anims:
    act = bpy.data.actions[act_name]
    rig.animation_data.action = act
    f0, f1 = act.frame_range
    span = f1 - f0
    layout["anims"][anim] = {"slot": slot, "frames": n, "fps": fps, "loop": loop}
    for d in range(A.DIRS):
        theta = d * math.tau / A.DIRS
        rig.parent.rotation_euler = (0, 0, math.pi / 2 - theta)
        r = slot // A.SLOTS_PER_ROW
        c0 = (slot % A.SLOTS_PER_ROW) * A.SLOT
        for i in range(n):
            t = i / n if loop else i / max(1, n - 1)
            sc.frame_set(int(round(f0 + span * t)))
            bpy.context.view_layer.update()
            sc.render.filepath = tmp_png
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(tmp_png, check_existing=False)
            px = np.empty(F * F * 4, dtype=np.float32)
            img.pixels.foreach_get(px)
            bpy.data.images.remove(img)
            sheet[r * F:(r + 1) * F, (c0 + i) * F:(c0 + i + 1) * F] = px.reshape(F, F, 4)[::-1]
        slot += 1
    print(f"  {AD}: {anim} tamam", flush=True)
rig.animation_data.action = None
rig.parent.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
co = world_to_camera_view(sc, sc.camera, Vector((0, 0, 0)))
layout["pivot"] = [round(co.x * F, 1), round((1 - co.y) * F, 1)]
h, w = sheet.shape[:2]
out_img = bpy.data.images.new(AD + "_sheet", w, h, alpha=True)
out_img.pixels.foreach_set(sheet[::-1].ravel())
os.makedirs(OUT, exist_ok=True)
png = os.path.join(OUT, f"{AD}_sprite_sheet.png")
out_img.filepath_raw = png
out_img.file_format = "PNG"
out_img.save()
with open(os.path.join(OUT, f"{AD}_sprite_sheet.json"), "w") as f:
    json.dump(layout, f, indent=1)
print("YAZILDI", png, flush=True)
