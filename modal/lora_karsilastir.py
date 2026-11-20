"""Stil LoRA karşılaştırması: aynı tarif + aynı seed ile LoRA'sız ve LoRA'lı üretim, yan yana görsel.
karsilastir.yml içinde KARS_MODUL=lora_karsilastir ile çalışır (deneme motoru, canlıya dokunmaz).
Çıktı: kars_lora_*.png ve kars_yan_yana.png"""
import base64
import io
import os
import time

from PIL import Image, ImageDraw, ImageFont

SEED = int(os.environ.get("SEED", "42"))
OZET = os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null")
NEG = ("text, watermark, blurry, cropped, multiple characters, character sheet, reference sheet, model sheet, multiple poses, "
       "multiple views, duplicate, turnaround, ground shadow, cast shadow, drop shadow, frame, border, scenery, landscape")
BG = "isolated on a plain flat solid medium gray background, no shadow, no ground, no scenery"
FRONT = "front view facing the camera"
TEK = "solo, one single character alone, full body 2D game character, centered, whole body visible"
# (ad, tarif, [(etiket, lora, ağırlık), ...])  — stil metinleri sitedeki STIL tablosuyla aynı
TESTLER = [
    ("cizgi_film", f"young woman adventurer with long red hair, green tunic and brown boots, {TEK}, 2D cartoon game art, clean bold outlines, flat colors, {FRONT}, {BG}",
     [("LoRA yok", None, None), ("cartoon 0.8", "cartoon", 0.8), ("cartoon2 1.5", "cartoon2", 1.5)]),
    ("chibi", f"young knight boy with a sword and round shield, {TEK}, cute chibi style 2D game art, big head small body, clean outlines, {FRONT}, {BG}",
     [("LoRA yok", None, None), ("chibi 0.85", "chibi", 0.85)]),
    ("karanlik", f"undead skeleton knight with a cursed glowing sword, {TEK}, dark fantasy 2D game art, moody desaturated colors, strong outlines, {FRONT}, {BG}",
     [("LoRA yok", None, None), ("dark 0.8", "dark", 0.8)]),
    ("hd", f"lion-headed warrior man in golden armor holding a spear, {TEK}, high quality 2D game art, hand painted, detailed shading, {FRONT}, {BG}",
     [("LoRA yok", None, None), ("detay 1.5", "detay", 1.5)]),
]


def yaz(m):
    print(m, flush=True)
    open(OZET, "a").write(f"- {m}\n")


def calistir(yeni):
    satirlar = []
    for ad, prompt, varyantlar in TESTLER:
        hucre = []
        for etiket, lora, w in varyantlar:
            b = {"prompt": prompt, "negative": NEG, "seed": SEED, "n": 1, "width": 832, "height": 1216,
                 "style": "other", "auto": False}
            if lora:
                b["lora"], b["lora_weight"] = lora, w
            t = time.time()
            d = yeni(b)
            im = Image.open(io.BytesIO(base64.b64decode(d["images"][0]))).convert("RGB")
            im.save(f"kars_lora_{ad}_{(lora or 'yok')}.png")
            yaz(f"{ad} / {etiket}: GPU {d['seconds']} sn (toplam {round(time.time() - t)} sn)")
            hucre.append((etiket, im))
        satirlar.append((ad, hucre))

    H = 512
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except Exception:  # noqa
        font = ImageFont.load_default()
    kucuk = [(ad, [(e, im.resize((int(im.width * H / im.height), H))) for e, im in hc]) for ad, hc in satirlar]
    W = max(sum(im.width + 10 for _, im in hc) for _, hc in kucuk) + 20
    tuval = Image.new("RGB", (W, 50 + len(kucuk) * (H + 70)), (30, 30, 34))
    dr = ImageDraw.Draw(tuval)
    dr.text((10, 10), f"Stil LoRA karsilastirmasi (DreamShaper XL, seed {SEED})", fill=(255, 255, 255), font=font)
    y = 50
    for ad, hc in kucuk:
        dr.text((10, y + 4), ad, fill=(255, 220, 120), font=font)
        x = 10
        for e, im in hc:
            dr.text((x, y + 34), e, fill=(180, 220, 255), font=font)
            tuval.paste(im, (x, y + 64))
            x += im.width + 10
        y += H + 70
    tuval.save("kars_yan_yana.png")
    yaz("Yan yana görsel hazır: kars_yan_yana.png")
