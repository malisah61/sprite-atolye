"""Motor deneme betiği (GitHub Actions'ta çalışır): üretim, referans, düzenleme, boyayarak düzenleme, dikişsiz doku."""
import base64
import io
import json
import os
import sys
import time
import urllib.request

URL = os.environ["MOTOR_URL"].rstrip("/")
KEY = os.environ.get("SPRITE_KEY", "")
OZET = os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null")
hatalar = []


def post(yol, body):
    req = urllib.request.Request(URL + yol, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Sprite-Key": KEY})
    t = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=900))
    return d, round(time.time() - t)


def kaydet(ad, b64):
    open(f"test_{ad}.png", "wb").write(base64.b64decode(b64))


def yaz(msg):
    print(msg)
    open(OZET, "a").write(f"- {msg}\n")


def dene(ad, fn):
    try:
        fn()
    except Exception as e:  # noqa
        hatalar.append(ad)
        yaz(f"❌ {ad}: {e}")


print(urllib.request.urlopen(URL + "/", timeout=900).read().decode())
ana = {}


def uret():
    d, s = post("/generate", {"prompt": "pixel art, green zombie, solo, one single character alone, full body 2D game character, front view, plain flat solid medium gray background",
                              "seed": 42, "n": 2, "width": 832, "height": 1216, "style": "pixel", "auto": True})
    for k, im in enumerate(d["images"]):
        kaydet(f"1_{k}", im)
    ana["img"] = d["images"][0]
    yaz(f"Üretim: {len(d['images'])} görsel, GPU {d['seconds']} sn, toplam {s} sn")


def referans():
    d, s = post("/generate", {"prompt": "pixel art, the same green zombie seen from the back, back view, solo, full body 2D game character, plain flat solid medium gray background",
                              "seed": 7, "n": 1, "width": 832, "height": 1216, "style": "pixel", "auto": True,
                              "reference": ana["img"], "ref_scale": 0.7})
    kaydet("ref_arka", d["images"][0])
    yaz(f"Referansla (arkadan): GPU {d['seconds']} sn")


def duzenle():
    d, s = post("/edit", {"image": ana["img"], "prompt": "pixel art, green zombie wearing a red baseball cap, full body",
                          "strength": 0.55, "style": "pixel", "seed": 3})
    kaydet("duzenle_sapka", d["images"][0])
    yaz(f"Metinle düzenleme: GPU {d['seconds']} sn")


def boya():
    from PIL import Image, ImageDraw

    im = Image.open(io.BytesIO(base64.b64decode(ana["img"])))
    m = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(m).rectangle([0, 0, im.width, int(im.height * 0.25)], fill=(255, 255, 255, 255))
    buf = io.BytesIO(); m.save(buf, format="PNG")
    d, s = post("/edit", {"image": ana["img"], "mask": base64.b64encode(buf.getvalue()).decode(),
                          "prompt": "pixel art, green zombie head wearing a viking helmet with horns", "style": "pixel", "seed": 5})
    kaydet("boya_migfer", d["images"][0])
    yaz(f"Boyayarak düzenleme: GPU {d['seconds']} sn")


def doku():
    d, s = post("/generate", {"prompt": "hand painted 2D game texture, seamless tileable lush green grass ground with small flowers and pebbles, top-down view, even lighting, flat, no shadows", "seed": 9, "n": 1,
                              "width": 1024, "height": 1024, "style": "other", "tileable": True})
    kaydet("doku_cimen", d["images"][0])
    yaz(f"Dikişsiz doku: GPU {d['seconds']} sn")


dene("üretim", uret)
if "img" in ana:
    dene("referans", referans)
    dene("düzenleme", duzenle)
    dene("boyayarak düzenleme", boya)
def karisik():
    d, s = post("/generate", {"prompt": "long snake body with no legs and no arms, coiled scaly tail, monkey head with red eyes and fangs, solo, one single creature alone, full body 2D game enemy, high quality 2D game art, side view, simple background, isolated on a plain flat solid medium gray background",
                              "seed": 33, "n": 1, "width": 1216, "height": 832, "style": "other", "auto": True,
                              "parts": [{"name": "head", "want": "monkey head with red eyes and fangs"}], "base": "snake", "absent": ["legs", "arms"],
                              "style_text": "high quality 2D game art, hand painted"})
    kaydet("karisik_maymun_yilan", d["images"][0])
    yaz(f"Otomatik parça kontrolü: {d.get('fixes')} · GPU {d['seconds']} sn")


dene("doku", doku)
dene("karışık yaratık", karisik)
sys.exit(1 if hatalar else 0)
