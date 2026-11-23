"""Blender yön render'larını motorla yeniden boyar: render = şekil/poz iskeleti (img2img), orijinal görsel = kimlik
(IP-Adapter referansı). Böylece 3D'nin tutarlı yönleri + SDXL'in detayı birleşir.
Kullanım: python3 uc_boyut/boya.py klasor orijinal.png "tarif" stil(cartoon|hd|pixel|...) guc"""
import base64
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modal"))
from motor_istemci import cagir  # noqa: E402

k, orj, tarif, stil, guc = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
URL = os.environ["MOTOR_URL"].rstrip("/")
KEY = os.environ.get("SPRITE_KEY", "")
b64 = lambda f: base64.b64encode(open(f, "rb").read()).decode()
fs = sorted(glob.glob(f"{k}/yon_*.png"))
n = len(fs)
for i, f in enumerate(fs):
    a = round(i * 360 / n) % 360
    bakis = ("front view facing the camera" if a == 0 else "back view seen from behind, facing away from the camera" if a == 180
             else "side view profile" if a in (90, 270) else "three-quarter view")
    body = {"image": b64(f), "prompt": f"{tarif}, {bakis}, full body, isolated on a plain flat solid medium gray background",
            "strength": guc, "style": "pixel" if stil == "pixel" else "other", "reference": b64(orj), "ref_scale": 0.5,
            "seed": 11, "auto": True}
    if stil in ("cartoon", "chibi"):
        body["lora"] = stil
    d = cagir(URL, "edit", body, KEY)  # iş kuyruğu (150 sn sınırı)
    out = f.replace("yon_", "boyali_")
    open(out, "wb").write(base64.b64decode(d["images"][0]))
    print(f"{os.path.basename(out)}: {bakis} · GPU {d['seconds']} sn", flush=True)
