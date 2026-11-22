"""Temizlik hata ayıklama (GPU'suz, GitHub Actions CPU'sunda): bir görseli motorun temizlik adımlarından
geçirip her adımın çıktısını kaydeder. Kullanım: python3 modal/temizlik_dene.py giris.png cikis_klasoru"""
import os
import sys

import numpy as np
from PIL import Image
from rembg import new_session, remove

sys.path.insert(0, os.path.dirname(__file__))
from app import border_bg, defringe, drop_debris, fill_holes  # noqa: E402

giris, cikis = sys.argv[1], sys.argv[2]
os.makedirs(cikis, exist_ok=True)
im = Image.open(giris).convert("RGB")
rgb = np.array(im)
bg = border_bg(rgb)
w = 24
edge = np.concatenate([rgb[:w].reshape(-1, 3), rgb[-w:].reshape(-1, 3), rgb[:, :w].reshape(-1, 3), rgb[:, -w:].reshape(-1, 3)]).astype(np.int32)
busy = float((np.sqrt(((edge - np.median(edge, axis=0)) ** 2).sum(-1)) > 40).mean())
print(f"arka plan rengi {bg}, kenar karışıklığı {busy:.3f} (düz sayılır: {busy < 0.15})")
rb = new_session("isnet-general-use")
adimlar = {}
adimlar["1_rembg"] = raw = remove(im, session=rb, post_process_mask=True)
adimlar["1b_rembg_islemsiz"] = remove(im, session=rb)
adimlar["2_delik_doldur"] = out = fill_holes(rgb, raw, bg)
adimlar["3_kenar_temizle"] = d = defringe(out, bg=bg)
adimlar["4_kirinti_sil"] = drop_debris(d)
import time
for model in ["birefnet-general", "birefnet-general-lite"]:
    try:
        t = time.time()
        ses = new_session(model)
        t1 = time.time()
        r = remove(im, session=ses, post_process_mask=True)
        print(f"{model}: yükleme {t1 - t:.1f} sn, kesim {time.time() - t1:.1f} sn (CPU)")
        adimlar[f"5_{model}"] = r
        adimlar[f"5_{model}_temiz"] = drop_debris(defringe(fill_holes(rgb, r, bg), bg=bg))
    except Exception as e:  # noqa
        print(f"{model} olmadı: {e}")
alan = lambda x: int((np.array(x)[..., 3] > 0).sum())
for ad, x in adimlar.items():
    x.save(f"{cikis}/{ad}.png")
    print(f"{ad}: opak alan {alan(x)}")
