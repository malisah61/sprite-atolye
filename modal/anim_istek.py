"""Canlı animasyon motoruna (/animate) istek atar: kareler + sprite sayfası + GIF.
Kullanım (Actions: anim_uret.yml): ANIM_URL, SPRITE_KEY ortamda; python3 modal/anim_istek.py ad tur [referans.png]
Ortam: TARIF, STIL (pixel|other), LORA, N, SEED, YON"""
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

from PIL import Image

URL = os.environ["ANIM_URL"].rstrip("/")
ad, turler = sys.argv[1], sys.argv[2].split(",")
ref = sys.argv[3] if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
os.makedirs("/tmp/out", exist_ok=True)
H = {"Content-Type": "application/json", "X-Sprite-Key": os.environ.get("SPRITE_KEY", "")}


def is_calistir(body):
    """İş kuyruğu: POST /is/animate → id, GET /is/<id> yoklanır (Modal 150 sn sınırına takılmaz)."""
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/is/animate", data=json.dumps(body).encode(), headers=H), timeout=300))
    except urllib.error.HTTPError as e:
        print("Motor hatası:", e.code, e.read().decode(errors="replace")[:2000]); raise
    son = time.time() + 1200
    while time.time() < son:
        time.sleep(5)
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/is/" + r["is"], headers=H), timeout=120))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RuntimeError("iş kayboldu (motor yeniden başladı)")
            continue
        except Exception:  # noqa — anlık kopma
            continue
        if d["durum"] == "calisiyor":
            continue
        if d["durum"] == "hata":
            raise RuntimeError(f"Motor: {d.get('kod')} {d.get('detay')}")
        return d["sonuc"]
    raise RuntimeError("zaman aşımı")
ozet = open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a")
for tur in turler:
    body = {"anim": tur, "prompt": os.environ.get("TARIF", ""), "style": os.environ.get("STIL", "other"),
            "seed": int(os.environ.get("SEED", "7")), "yon": int(os.environ.get("YON", "1")), "poz": True}
    if os.environ.get("N"):
        body["n"] = int(os.environ["N"])
    if os.environ.get("LORA"):
        body["lora"] = os.environ["LORA"]
    if ref:
        body["image"] = base64.b64encode(open(ref, "rb").read()).decode()
    t0 = time.time()
    d = is_calistir(body)
    kareler = [Image.open(io.BytesIO(base64.b64decode(f))).convert("RGBA") for f in d["frames"]]
    for i, k in enumerate(kareler):
        k.save(f"/tmp/out/{ad}_{tur}_{i}.png")
    Image.open(io.BytesIO(base64.b64decode(d["reference"]))).save(f"/tmp/out/{ad}_{tur}_referans.png")
    w, h = kareler[0].size
    sayfa = Image.new("RGBA", (w * len(kareler), h), (0, 0, 0, 0))
    for i, k in enumerate(kareler):
        sayfa.alpha_composite(k, (i * w, 0))
    sayfa.save(f"/tmp/out/{ad}_{tur}_sayfa.png")
    gif = []
    for k in kareler:
        bg = Image.new("RGBA", k.size, (90, 90, 90, 255)); bg.alpha_composite(k)
        gif.append(bg.convert("RGB").resize((max(1, w // 2), max(1, h // 2))))
    gif[0].save(f"/tmp/out/{ad}_{tur}.gif", save_all=True, append_images=gif[1:], duration=110, loop=0)
    msg = f"{tur}: {len(kareler)} kare {w}×{h}, GPU {d['seconds']} sn ({d.get('sure')}), toplam {round(time.time() - t0)} sn"
    print(msg, flush=True); ozet.write(f"- {msg}\n")
