"""Sipariş sistemi yardımcıları (GitHub Actions'tan çağrılır).

  python3 siparis/siparis.py liste hedef/assets/siparis.json [sadece]   → GITHUB_OUTPUT'a matrix (ad listesi)
  python3 siparis/siparis.py uret hedef/assets/siparis.json AD cikis     → motorla görsel(ler) üretir, en iyisini seçer

siparis.json biçimi (liste):
  {"ad": "alman_dag", "tarif": "İngilizce tarif", "tur": "karakter|dusman|esya|...", "stil": "other|pixel|cartoon|chibi|dark",
   "adet": 2, "seed": 7, "hat": "komando" (isteğe bağlı: 3D + UAL ile 8 yön sprite sayfası), "ekipman": ["rifle", "helmet"],
   "boyut": [1024, 1024], "aday": 2 (isteğe bağlı: elle aday seçimi), "cikti": "assets/sprites/alman_dag_sprite_sheet.png" (isteğe bağlı hedef yol)}
"""
import base64
import json
import os
import re
import sys
import time
import urllib.request

MOTOR = os.environ.get("MOTOR_URL", "https://malisah61--sprite-atolye-motor-web.us-east.modal.run")

# Komando hattı için: TripoSR'ın iyi 3D çıkarması ve iskelete oturması için T-poz, önden, tek figür
KOMANDO_EK = ("full body character, standing in a T-pose with both arms stretched straight out horizontally to the sides, "
              "legs slightly apart, facing the viewer, front view, symmetrical, empty hands, plain light grey background, "
              "realistic proportions, 3d game character render, soft even lighting")
VARSAYILAN_NEG = ("text, watermark, blurry, cropped, multiple characters, character sheet, reference sheet, model sheet, "
                  "multiple poses, multiple views, duplicate, turnaround, ground shadow, cast shadow, drop shadow, frame, border, "
                  "patterned background, scenery, landscape")
KOMANDO_NEG = VARSAYILAN_NEG + ", " + "holding weapon, gun in hands, side view, back view, cut off feet, arms down, crossed arms"
LORA = {"cartoon": "cartoon", "chibi": "chibi", "dark": "dark"}


def oku(yol):
    d = json.load(open(yol))
    return d["siparisler"] if isinstance(d, dict) else d


def temiz_ad(s):
    return re.sub(r"[^a-z0-9_-]", "-", s.lower())


def liste(yol, sadece=""):
    s = oku(yol)
    istek = {x.strip() for x in sadece.split(",") if x.strip()}
    adlar = [temiz_ad(x["ad"]) for x in s if not istek or temiz_ad(x["ad"]) in istek]
    out = os.environ.get("GITHUB_OUTPUT")
    satir = "adlar=" + json.dumps(adlar)
    print(satir)
    if out:
        open(out, "a").write(satir + "\n")


def istek(yol, govde, deneme=3):
    for i in range(deneme):
        try:
            req = urllib.request.Request(MOTOR + yol, data=json.dumps(govde).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "X-Sprite-Key": os.environ["SPRITE_KEY"]})
            return json.load(urllib.request.urlopen(req, timeout=1200))
        except Exception as e:  # motor soğuk başlarken / sırada beklerken ara ara düşebilir
            print(f"motor hatası ({i + 1}/{deneme}): {e}", flush=True)
            time.sleep(20)
    raise SystemExit("motor cevap vermedi")


def genislik_orani(png_bytes):
    """Saydam olmayan alanın en/boy oranı (T-pozda kollar açık → geniş)."""
    import io

    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    b = im.getchannel("A").point(lambda a: 255 if a > 40 else 0).getbbox()
    if not b:
        return 0
    return (b[2] - b[0]) / max(1, b[3] - b[1])


def figur_sayisi(png_bytes):
    """Yan yana iki kişi çizildi mi? (23 Kasım: madenci adayı iki kişiydi, birbirine değiyordu)
    Sütun doluluk profilinin ortasında (%30-70) derin bir çukur, iki yanında yüksek tepeler → 2."""
    import io

    from PIL import Image
    a = Image.open(io.BytesIO(png_bytes)).convert("RGBA").getchannel("A")
    b = a.getbbox()
    if not b:
        return 0
    a = a.crop(b)
    w, h = a.size
    px = a.load()
    c = [sum(1 for y in range(0, h, 4) if px[x, y] > 40) for x in range(w)]
    tepe = max(c) or 1
    i0, i1 = int(w * 0.3), int(w * 0.7)
    if i1 <= i0:
        return 1
    m = min(range(i0, i1), key=lambda x: c[x])
    sol, sag = max(c[:m] or [0]), max(c[m:] or [0])
    if sol > 0.5 * tepe and sag > 0.5 * tepe and c[m] < 0.25 * min(sol, sag):
        return 2
    return 1


def uret(yol, ad, cikis):
    s = [x for x in oku(yol) if temiz_ad(x["ad"]) == ad][0]
    os.makedirs(cikis, exist_ok=True)
    stil = s.get("stil", "other")
    komando = s.get("hat") == "komando"
    tarif = s["tarif"]
    w, h = s.get("boyut", [1024, 1024])
    govde = {"prompt": f"{tarif}, {KOMANDO_EK}" if komando else tarif,
             "style": "pixel" if stil == "pixel" else "other",
             "n": max(1, min(4, int(s.get("adet", 2)))), "seed": int(s.get("seed", 7)),
             "width": int(w), "height": int(h), "auto": True, "hires": bool(s.get("ekstra", False))}
    if komando:
        govde["negative"] = KOMANDO_NEG
    if stil in LORA:
        govde["lora"] = LORA[stil]
    t0 = time.time()
    onceki = os.environ.get("ONCEKI_DIR", "")
    if onceki and os.path.exists(f"{onceki}/{ad}/gorsel.png"):
        # önceki siparişin adaylarını yeniden kullan (motor harcaması yok; seçim + 3D/render tekrarı)
        import glob
        fs = sorted(glob.glob(f"{onceki}/{ad}/aday_*.png")) or [f"{onceki}/{ad}/gorsel.png"]
        print(f"önceki görseller kullanılıyor: {fs}")
        d = {"images": [base64.b64encode(open(f, "rb").read()).decode() for f in fs], "seconds": 0}
    else:
        d = istek("/generate", govde)
    resimler = [base64.b64decode(x) for x in d["images"]]
    puan = d.get("puan") or [None] * len(resimler)
    for k, r in enumerate(resimler):
        open(f"{cikis}/aday_{k + 1}.png", "wb").write(r)
    # seçim: motor en iyiyi başa koyar; Komando hattında T-poz (en geniş figür) tercih edilir
    sec = 0
    if komando and len(resimler) > 1:
        oran = [genislik_orani(r) for r in resimler]
        figur = [figur_sayisi(r) for r in resimler]
        print("figür sayıları:", figur)
        oran = [o if f == 1 else 9.0 for o, f in zip(oran, figur)]   # çok kişili aday seçilmez
        print("en/boy oranları:", [round(o, 2) for o in oran])
        # gerçek T-poz (kollar açık, oran > 0.8) varsa o; yoksa BOYDAN (ayaklar dahil, ince uzun: oran < 0.5)
        # adaylar arasında motorun en iyisi. Belden kesik / eller belde (geniş) adaylar 3D'de bozuk çıkıyor
        # (23 Kasım: nişancı belden kesik geldi → gövde topak oldu).
        # Kollar aşağıdaysa Komando hattı mankenin kollarını indirip modeli T-poza kendisi açar.
        tp = [i for i in range(len(resimler)) if oran[i] > 0.8]
        boy = [i for i in range(len(resimler)) if oran[i] < 0.5]
        sec = tp[0] if tp else (boy[0] if boy else min(range(len(resimler)), key=lambda i: oran[i]))
    if s.get("aday") and 1 <= int(s["aday"]) <= len(resimler):
        sec = int(s["aday"]) - 1   # elle seçim (siparis.json: "aday": 2)
    open(f"{cikis}/gorsel.png", "wb").write(resimler[sec])
    bilgi = {"ad": ad, "tarif": tarif, "secilen": sec + 1, "puan": puan, "gpu_sn": d.get("seconds"),
             "toplam_sn": round(time.time() - t0), "dersler": d.get("dersler"), "hat": s.get("hat", ""),
             "ekipman": s.get("ekipman", []), "cikti": s.get("cikti", "")}
    json.dump(bilgi, open(f"{cikis}/bilgi.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(bilgi, ensure_ascii=False))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        open(out, "a").write(f"hat={s.get('hat', '')}\nekipman={','.join(s.get('ekipman', []))}\n")


if __name__ == "__main__":
    k = sys.argv[1]
    if k == "liste":
        liste(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    elif k == "uret":
        uret(sys.argv[2], sys.argv[3], sys.argv[4])
