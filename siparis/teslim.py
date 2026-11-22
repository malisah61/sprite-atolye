"""Sipariş çıktılarını hedef repoya yerleştirir.
python3 siparis/teslim.py /tmp/cikti /tmp/hedef

Her <ad>/bilgi.json için:
 - Komando hattı: <ad>_sprite_sheet.png/.json → "cikti" verildiyse onun klasörüne, yoksa assets/sprites/
 - diğerleri: gorsel.png → "cikti" yolu, yoksa assets/uretilen/<ad>.png
"""
import glob
import json
import os
import shutil
import sys

kaynak, hedef = sys.argv[1], sys.argv[2]
for b in sorted(glob.glob(f"{kaynak}/*/bilgi.json")):
    d = os.path.dirname(b)
    bilgi = json.load(open(b))
    ad = bilgi["ad"]
    if bilgi.get("hat") == "komando":
        png = f"{d}/{ad}_sprite_sheet.png"
        if not os.path.exists(png):
            print(f"{ad}: sprite sayfası yok, atlandı")
            continue
        yer = os.path.dirname(bilgi.get("cikti") or "assets/sprites/x.png")
        os.makedirs(f"{hedef}/{yer}", exist_ok=True)
        for uz in (".png", ".json"):
            shutil.copy(png.replace(".png", uz), f"{hedef}/{yer}/{ad}_sprite_sheet{uz}")
        os.makedirs(f"{hedef}/assets/uretilen/{ad}", exist_ok=True)
        for f in ("gorsel.png", "onizleme.png", "bilgi.json"):
            if os.path.exists(f"{d}/{f}"):
                shutil.copy(f"{d}/{f}", f"{hedef}/assets/uretilen/{ad}/{f}")
        print(f"{ad}: {yer}/{ad}_sprite_sheet.png")
    else:
        yol = bilgi.get("cikti") or f"assets/uretilen/{ad}.png"
        os.makedirs(os.path.dirname(f"{hedef}/{yol}"), exist_ok=True)
        shutil.copy(f"{d}/gorsel.png", f"{hedef}/{yol}")
        print(f"{ad}: {yol}")
