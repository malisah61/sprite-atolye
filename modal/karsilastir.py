"""Model karşılaştırma: aynı tarif + aynı seed ile eski (canlı) ve yeni (deneme) motoru yan yana üretir.
GitHub Actions'ta çalışır (karsilastir.yml). Çıktı: kars_*.png ve kars_yan_yana.png"""
import base64
import io
import json
import os
import sys
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

# Modal uzun süren isteklerde (soğuk başlangıç) 303 ile aynı adrese yönlendirir; urllib'in döngü sınırını büyüt
urllib.request.HTTPRedirectHandler.max_repeats = 200
urllib.request.HTTPRedirectHandler.max_redirections = 200

ESKI = os.environ["ESKI_URL"].rstrip("/")
YENI = os.environ["YENI_URL"].rstrip("/")
KEY = os.environ.get("SPRITE_KEY", "")
SEED = int(os.environ.get("SEED", "42"))
OZET = os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null")
BG = "isolated on a plain flat solid medium gray background, no shadow, no ground, no scenery"
FRONT = "front view facing the camera"
TARIFLER = [
    ("pixel_zombi", "pixel", 832, 1216,
     f"pixel art, green zombie with torn clothes, solo, one single creature alone, full body 2D game enemy, centered, whole body visible, pixel art, crisp pixels, limited color palette, retro game sprite, {FRONT}, {BG}"),
    ("cizgi_kadin", "other", 832, 1216,
     f"young woman adventurer with long red hair, green tunic and brown boots, solo, one single character alone, full body 2D game character, centered, whole body visible, 2D cartoon game art, clean bold outlines, flat colors, {FRONT}, {BG}"),
    ("hd_aslan", "other", 832, 1216,
     f"lion-headed warrior man in golden armor holding a spear, solo, one single character alone, full body 2D game character, centered, whole body visible, high quality 2D game art, hand painted, detailed shading, {FRONT}, {BG}"),
    ("esya_kilic", "other", 1024, 1024,
     f"glowing magic sword with blue runes on the blade, single 2D game item asset, one object, centered, high quality 2D game art, hand painted, detailed shading, {FRONT}, {BG}"),
]


def yaz(m):
    print(m, flush=True)
    open(OZET, "a").write(f"- {m}\n")


def post(url, yol, body):
    req = urllib.request.Request(url + yol, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Sprite-Key": KEY})
    for deneme in range(3):
        try:
            return json.load(urllib.request.urlopen(req, timeout=900))
        except Exception as e:  # noqa
            yaz(f"tekrar ({deneme + 1}): {e}")
            time.sleep(10)
    raise RuntimeError("motor cevap vermedi")


def b2i(b):
    return Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB")


for u in (ESKI, YENI):
    for deneme in range(5):
        try:
            print(urllib.request.urlopen(u + "/", timeout=900).read().decode(), flush=True)
            break
        except Exception as e:  # noqa
            yaz(f"motor uyanıyor ({u}): {e}")
            time.sleep(15)

sonuc = {}
for ad, stil, w, h, prompt in TARIFLER:
    for etiket, url in (("eski", ESKI), ("yeni", YENI)):
        d = post(url, "/generate", {"prompt": prompt, "seed": SEED, "n": 1, "width": w, "height": h, "style": stil, "auto": False})
        im = b2i(d["images"][0])
        im.save(f"kars_{ad}_{etiket}.png")
        sonuc[(ad, etiket)] = im
        yaz(f"{ad} / {etiket}: GPU {d['seconds']} sn")

# IP-Adapter + yeni model: aynı zombi arkadan
ref = open("kars_pixel_zombi_yeni.png", "rb").read()
d = post(YENI, "/generate", {"prompt": f"pixel art, the same green zombie seen from the back, back view, solo, full body 2D game enemy, {BG}",
                             "seed": 7, "n": 1, "width": 832, "height": 1216, "style": "pixel", "auto": True,
                             "reference": base64.b64encode(ref).decode(), "ref_scale": 0.7})
Image.open(io.BytesIO(base64.b64decode(d["images"][0]))).save("kars_yeni_referans_arka.png")
yaz(f"yeni / referans (IP-Adapter): GPU {d['seconds']} sn")

# yan yana karşılaştırma görseli: satır = tarif, sütun = eski | yeni
H = 512
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
except Exception:  # noqa
    font = ImageFont.load_default()
satirlar = []
for ad, *_ in TARIFLER:
    hucre = [sonuc[(ad, e)].resize((int(sonuc[(ad, e)].width * H / sonuc[(ad, e)].height), H)) for e in ("eski", "yeni")]
    satirlar.append((ad, hucre))
W = max(sum(c.width for c in hc) for _, hc in satirlar) + 30
tuval = Image.new("RGB", (W, 50 + len(satirlar) * (H + 40)), (30, 30, 34))
dr = ImageDraw.Draw(tuval)
model = os.environ.get("YENI_MODEL", "yeni")
dr.text((10, 10), f"SOL: SDXL base (eski)   SAG: {model} (yeni)   seed {SEED}", fill=(255, 255, 255), font=font)
y = 50
for ad, hc in satirlar:
    dr.text((10, y + 4), ad, fill=(255, 220, 120), font=font)
    x = 10
    for c in hc:
        tuval.paste(c, (x, y + 36))
        x += c.width + 10
    y += H + 40
tuval.save("kars_yan_yana.png")
yaz("Yan yana görsel hazır: kars_yan_yana.png")
sys.exit(0)
