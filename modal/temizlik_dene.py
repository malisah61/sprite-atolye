"""Temizlik hata ayıklama (GPU'suz, GitHub Actions CPU'sunda): bir görseli motorun temizlik adımlarından
geçirip her adımın çıktısını kaydeder. Kullanım: python3 modal/temizlik_dene.py giris.png cikis_klasoru"""
import os
import sys

import numpy as np
from PIL import Image
from rembg import new_session, remove

sys.path.insert(0, os.path.dirname(__file__))
from app import REMBG_MODEL, border_bg, defringe, drop_debris, fill_holes  # noqa: E402

giris, cikis = sys.argv[1], sys.argv[2]
os.makedirs(cikis, exist_ok=True)
im = Image.open(giris).convert("RGB")
rgb = np.array(im)
bg = border_bg(rgb)
w = 24
edge = np.concatenate([rgb[:w].reshape(-1, 3), rgb[-w:].reshape(-1, 3), rgb[:, :w].reshape(-1, 3), rgb[:, -w:].reshape(-1, 3)]).astype(np.int32)
busy = float((np.sqrt(((edge - np.median(edge, axis=0)) ** 2).sum(-1)) > 40).mean())
print(f"arka plan rengi {bg}, kenar karışıklığı {busy:.3f} (düz sayılır: {busy < 0.15})")
import time
t0 = time.time()
rb = new_session(REMBG_MODEL)
print(f"model: {REMBG_MODEL}")
adimlar = {}
adimlar["1_rembg"] = raw = remove(im, session=rb, post_process_mask=True)
print(f"kesim {time.time() - t0:.1f} sn (yükleme dahil)")
adimlar["1b_isnet_eski"] = remove(im, session=new_session("isnet-general-use"), post_process_mask=True)
adimlar["2_delik_doldur"] = out = fill_holes(rgb, raw, bg)
adimlar["3_kenar_temizle"] = d = defringe(out, bg=bg)
adimlar["4_kirinti_sil"] = drop_debris(d)
alan = lambda x: int((np.array(x)[..., 3] > 0).sum())
for ad, x in adimlar.items():
    x.save(f"{cikis}/{ad}.png")
    print(f"{ad}: opak alan {alan(x)}")
