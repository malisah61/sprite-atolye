"""Blender çıktılarını tek sprite sayfasına (yan yana) ve teşhis sayfasına dizer. python3 uc_boyut/sayfa.py klasor"""
import glob
import sys

from PIL import Image

k = sys.argv[1]
for desen, ad in (("yon_*.png", "sayfa_yonler.png"), ("eksen_*.png", "sayfa_eksen.png")):
    fs = sorted(glob.glob(f"{k}/{desen}"))
    if not fs:
        continue
    ims = [Image.open(f).convert("RGBA") for f in fs]
    w, h = ims[0].size
    out = Image.new("RGBA", (w * len(ims), h), (0, 0, 0, 0))
    for i, im in enumerate(ims):
        out.paste(im, (i * w, 0))
    out.save(f"{k}/{ad}")
    print(ad, [f.split("/")[-1] for f in fs])
