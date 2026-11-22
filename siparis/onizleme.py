"""Komando sprite sayfasından önizleme: her animasyonun güney (2) yönünden kareler + yürümenin 8 yönü, yeşil zemin üstünde.
python3 siparis/onizleme.py sayfa.png onizleme.png"""
import json
import sys

from PIL import Image

sayfa, cikis = sys.argv[1], sys.argv[2]
L = json.load(open(sayfa.replace(".png", ".json")))
im = Image.open(sayfa).convert("RGBA")
F, spr, S = L["frame"], L["slots_per_row"], L["slot"]


def kare(slot, i):
    r, c0 = slot // spr, (slot % spr) * S
    return im.crop(((c0 + i) * F, r * F, (c0 + i + 1) * F, (r + 1) * F))


satirlar = []
for ad, a in L["anims"].items():
    satirlar.append([kare(a["slot"] + 2, i) for i in range(a["frames"])])
w = L["anims"].get("walk")
if w:
    satirlar.append([kare(w["slot"] + d, 1) for d in range(L["directions"])])
cols = max(len(s) for s in satirlar)
out = Image.new("RGBA", (cols * F, len(satirlar) * F), (70, 120, 60, 255))
for y, s in enumerate(satirlar):
    for x, k in enumerate(s):
        out.alpha_composite(k, (x * F, y * F))
out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
out.convert("RGB").save(cikis)
print("önizleme:", cikis, out.size)
