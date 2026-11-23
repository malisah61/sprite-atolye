"""Motor deneme betiği (GitHub Actions'ta çalışır): üretim, referans, düzenleme, boyayarak düzenleme, dikişsiz doku."""
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

URL = os.environ["MOTOR_URL"].rstrip("/")
KEY = os.environ.get("SPRITE_KEY", "")
OZET = os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null")
hatalar = []


def post(yol, body):
    req = urllib.request.Request(URL + yol, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Sprite-Key": KEY})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=900))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:800]}")
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
    pu = d.get("puan") or []
    assert len(pu) == 2 and pu[0] >= pu[1], f"en iyisini seç çalışmadı: {pu}"
    yaz(f"Üretim: {len(d['images'])} görsel, GPU {d['seconds']} sn, toplam {s} sn · en iyisi başta, puanlar {pu}")


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


def lora_cizgi():
    d, s = post("/generate", {"prompt": "young woman adventurer with long red hair, green tunic and brown boots, solo, one single character alone, full body 2D game character, centered, 2D cartoon game art, clean bold outlines, flat colors, front view, isolated on a plain flat solid medium gray background",
                              "seed": 42, "n": 1, "width": 832, "height": 1216, "style": "other", "auto": True, "lora": "cartoon"})
    kaydet("lora_cizgi_film", d["images"][0])
    yaz(f"Stil LoRA (çizgi film) + otomatik temizlik: GPU {d['seconds']} sn")


def dersler():
    # Ders testi: pixel kavalcıda kaval sopaya dönüşüyordu → ders kuralı + taslak→pixel uygulanmalı
    d, s = post("/generate", {"prompt": "pixel art, Pied Piper of Hamelin, young human flute player, full body, playing a wooden flute at his lips, red and yellow medieval clothes, striped stockings, solo, plain flat solid medium gray background",
                              "seed": 23, "n": 1, "width": 832, "height": 1216, "style": "pixel", "auto": True})
    kaydet("ders_kavalci", d["images"][0])
    assert "kaval" in (d.get("dersler") or []), f"ders uygulanmadı: {d.get('dersler')}"
    assert d.get("iki_asama"), "taslak→pixel çalışmadı"
    yaz(f"Dersler: {d.get('dersler')} · taslak→pixel: {d.get('iki_asama')} · GPU {d['seconds']} sn")


def hires():
    # İki aşamalı üretim (hi-res fix): aynı tarif + seed, kapalı ve açık → süre farkı = ek maliyet
    b = {"prompt": "lion man warrior, muscular anthropomorphic lion with golden mane, leather armor, holding a battle axe, solo, one single character alone, full body 2D game character, high quality 2D game art, hand painted, detailed shading, front view, isolated on a plain flat solid medium gray background",
         "seed": 42, "n": 1, "width": 832, "height": 1216, "style": "other", "auto": True}
    d0, _ = post("/generate", b)
    kaydet("hires_kapali", d0["images"][0])
    d1, _ = post("/generate", {**b, "hires": True})
    kaydet("hires_acik", d1["images"][0])
    assert d1.get("hires"), "hires uygulanmadı"
    assert "tek silah" in (d1.get("dersler") or []), f"tek silah dersi uygulanmadı: {d1.get('dersler')}"
    yaz(f"Tek silah dersi: {d1.get('dersler')} · taslak seçimi {d1.get('fixes')} · puan {d1.get('puan')}")
    from PIL import Image
    w0 = Image.open(io.BytesIO(base64.b64decode(d0["images"][0]))).size
    w1 = Image.open(io.BytesIO(base64.b64decode(d1["images"][0]))).size
    yaz(f"Ekstra kalite (hi-res): kapalı {w0} GPU {d0['seconds']} sn · açık {w1} GPU {d1['seconds']} sn (büyütme {d1.get('hires_seconds')} sn)")


def yuz():
    # 0d Yüz düzeltme: aynı tarif + seed, yüz düzeltme kapalı / açık (Komando'ya uygun tarif: Alman nöbetçi)
    b = {"prompt": "WW2 German sentry soldier, adult man, field grey uniform, grey steel helmet, holding a rifle, solo, one single character alone, full body 2D game character, high quality 2D game art, hand painted, detailed shading, front view, isolated on a plain flat solid medium gray background",
         "seed": 17, "n": 1, "width": 832, "height": 1216, "style": "other", "auto": True, "hires": True}
    d0, _ = post("/generate", b)
    kaydet("yuz_kapali", d0["images"][0])
    d1, _ = post("/generate", {**b, "yuz": True})
    kaydet("yuz_acik", d1["images"][0])
    lg = (d1.get("yuz") or [{}])[0]
    assert lg.get("durum") == "düzeltildi", f"yüz düzeltilmedi: {d1.get('yuz')}"
    yaz(f"Yüz düzeltme: {lg} · kapalı GPU {d0['seconds']} sn · açık GPU {d1['seconds']} sn (yüz {d1.get('yuz_seconds')} sn)")
    # kadın çizgi film karakteri (yüz düzeltme açık)
    d2, _ = post("/generate", {"prompt": "young woman adventurer with long red hair, green tunic and brown boots, solo, one single character alone, full body 2D game character, centered, 2D cartoon game art, clean bold outlines, flat colors, front view, isolated on a plain flat solid medium gray background",
                               "seed": 42, "n": 1, "width": 832, "height": 1216, "style": "other", "auto": True, "lora": "cartoon", "hires": True, "yuz": True})
    kaydet("yuz_cizgi_kadin", d2["images"][0])
    yaz(f"Yüz düzeltme (çizgi film kadın): {d2.get('yuz')} · GPU {d2['seconds']} sn")


dene("yüz düzeltme", yuz)
dene("doku", doku)
dene("ekstra kalite", hires)
dene("dersler", dersler)
dene("stil LoRA", lora_cizgi)
dene("karışık yaratık", karisik)
sys.exit(1 if hatalar else 0)
