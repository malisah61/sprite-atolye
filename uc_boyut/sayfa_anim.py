"""Animasyon karelerini sprite sayfasına (satır = yön, sütun = kare) ve GIF önizlemeye dizer.
python3 uc_boyut/sayfa_anim.py klasor"""
import glob
import re
import sys

from PIL import Image

k = sys.argv[1]
fs = glob.glob(f"{k}/*_y*_k*.png")
anims = sorted({re.match(r"(.+)_y\d+_k\d+\.png", f.split("/")[-1]).group(1) for f in fs})
for a in anims:
    yon = 1 + max(int(re.search(r"_y(\d+)_", f).group(1)) for f in fs if f.split("/")[-1].startswith(a + "_y"))
    kare = 1 + max(int(re.search(r"_k(\d+)\.", f).group(1)) for f in fs if f.split("/")[-1].startswith(a + "_y"))
    ilk = Image.open(f"{k}/{a}_y0_k0.png")
    w, h = ilk.size
    sayfa = Image.new("RGBA", (w * kare, h * yon), (0, 0, 0, 0))
    for y in range(yon):
        for x in range(kare):
            sayfa.paste(Image.open(f"{k}/{a}_y{y}_k{x}.png").convert("RGBA"), (x * w, y * h))
    sayfa.save(f"{k}/sayfa_{a}.png")
    # önizleme GIF: tüm yönler yan yana, yeşil zemin
    kareler = []
    for x in range(kare):
        g = Image.new("RGBA", (w * yon // 2, h * 2), (40, 170, 60, 255))
        for y in range(yon):
            im = Image.open(f"{k}/{a}_y{y}_k{x}.png").convert("RGBA")
            g.alpha_composite(im, ((y % (yon // 2)) * w, (y // (yon // 2)) * h))
        kareler.append(g.convert("RGB").resize((g.width // 2, g.height // 2)))
    kareler[0].save(f"{k}/onizleme_{a}.gif", save_all=True, append_images=kareler[1:], duration=110, loop=0)
    print(f"{a}: {yon} yön × {kare} kare → sayfa_{a}.png, onizleme_{a}.gif")
