"""Yapay zekâ animasyonu için poz iskeletleri (OpenPose 18 nokta, COCO sırası) — kodla üretilir, GPU gerekmez.

Karakter YANDAN, sağa bakıyor. Sola bakan kareler aynalanarak elde edilir.
Koordinatlar: x sağa (ileri), y yukarı, birim = figür boyu (ayak bileği ~0, baş tepesi ~1).
Kullanım: kareler("yuru", 8) → [ {nokta_adı: (x, y) | None}, ... ];  ciz(kare, 768, 1024) → PIL RGB (siyah zemin)
"""
import math

# COCO-18 sırası (OpenPose)
ADLAR = ["burun", "boyun", "sag_omuz", "sag_dirsek", "sag_bilek", "sol_omuz", "sol_dirsek", "sol_bilek",
         "sag_kalca", "sag_diz", "sag_ayak", "sol_kalca", "sol_diz", "sol_ayak", "sag_goz", "sol_goz", "sag_kulak", "sol_kulak"]
# çizim sırası ve renkleri (controlnet_aux draw_bodypose ile aynı — ControlNet bu renklerle eğitildi)
UZUVLAR = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13),
           (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
RENKLER = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0),
           (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255),
           (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]

# vücut ölçüleri (figür boyuna oranla)
UYLUK, BALDIR = 0.245, 0.235
PAZU, ONKOL = 0.165, 0.16
KALCA_Y, OMUZ_Y, BOYUN_Y = 0.50, 0.805, 0.835


def _uc(nokta, aci, boy):
    """aci: aşağı dikeyden derece, + = ileri (sağa). Uzvun ucunu döner."""
    a = math.radians(aci)
    return (nokta[0] + math.sin(a) * boy, nokta[1] - math.cos(a) * boy)


def _bacak(kalca, uyluk_aci, diz_bukum):
    diz = _uc(kalca, uyluk_aci, UYLUK)
    ayak = _uc(diz, uyluk_aci - diz_bukum, BALDIR)  # diz bükülünce baldır geriye
    return diz, ayak


def _kol(omuz, pazu_aci, dirsek_bukum):
    dirsek = _uc(omuz, pazu_aci, PAZU)
    bilek = _uc(dirsek, pazu_aci + dirsek_bukum, ONKOL)  # dirsek bükülünce önkol ileri
    return dirsek, bilek


def _iskelet(govde_egim=0.0, bob=0.0, bacak_s=(0, 5), bacak_o=(0, 5), kol_s=(0, 10), kol_o=(0, 10), bas_egim=0.0,
             x0=0.0, yere_bas=True):
    """s = yakın (sağ) taraf, o = uzak (sol) taraf. govde_egim: + = öne eğik (derece)."""
    kalca = (x0, KALCA_Y + bob)
    g = math.radians(govde_egim)
    gl = BOYUN_Y - KALCA_Y
    boyun = (kalca[0] + math.sin(g) * gl, kalca[1] + math.cos(g) * gl)
    ol = OMUZ_Y - KALCA_Y
    omuz = (kalca[0] + math.sin(g) * ol, kalca[1] + math.cos(g) * ol)
    b = math.radians(govde_egim + bas_egim)
    bas_merkez = (boyun[0] + math.sin(b) * 0.075, boyun[1] + math.cos(b) * 0.075)
    ileri = (math.cos(b), -math.sin(b))  # başın baktığı yön
    burun = (bas_merkez[0] + ileri[0] * 0.06, bas_merkez[1] + ileri[1] * 0.06 - 0.005)
    goz = (bas_merkez[0] + ileri[0] * 0.045, bas_merkez[1] + ileri[1] * 0.045 + 0.02)
    kulak = (bas_merkez[0] - ileri[0] * 0.015, bas_merkez[1] - ileri[1] * 0.015 + 0.01)
    p = {"burun": burun, "boyun": boyun, "sag_goz": goz, "sol_goz": None, "sag_kulak": kulak, "sol_kulak": None}
    # yan görünüş: iki omuz/kalça neredeyse üst üste (uzak taraf çok az geride)
    p["sag_omuz"], p["sol_omuz"] = (omuz[0] + 0.005, omuz[1]), (omuz[0] - 0.015, omuz[1] + 0.003)
    p["sag_kalca"], p["sol_kalca"] = (kalca[0] + 0.005, kalca[1]), (kalca[0] - 0.012, kalca[1] + 0.003)
    p["sag_diz"], p["sag_ayak"] = _bacak(p["sag_kalca"], *bacak_s)
    p["sol_diz"], p["sol_ayak"] = _bacak(p["sol_kalca"], *bacak_o)
    p["sag_dirsek"], p["sag_bilek"] = _kol(p["sag_omuz"], kol_s[0] + govde_egim * 0.5, kol_s[1])
    p["sol_dirsek"], p["sol_bilek"] = _kol(p["sol_omuz"], kol_o[0] + govde_egim * 0.5, kol_o[1])
    if yere_bas:  # en alçak ayak yere (y=0.02) otursun
        dy = 0.02 - min(p["sag_ayak"][1], p["sol_ayak"][1])
        p = {k: (None if v is None else (v[0], v[1] + dy)) for k, v in p.items()}
    return p


def kareler(tur, n=None):
    """tur: bekleme | yuru | kos | saldir | zipla | hasar → poz listesi."""
    out = []
    if tur == "yuru":
        n = n or 8
        for i in range(n):
            t = 2 * math.pi * i / n
            def bacak(f):
                return (24 * math.sin(f), 6 + 40 * max(0.0, math.cos(f + 0.9)) ** 2)  # en çok bükülme: ayak yerden kalkınca
            out.append(_iskelet(govde_egim=3, bob=0.012 * math.cos(2 * t),
                                bacak_s=bacak(t), bacak_o=bacak(t + math.pi),
                                kol_s=(-20 * math.sin(t), 18 + 10 * max(0.0, -math.sin(t))),
                                kol_o=(-20 * math.sin(t + math.pi), 18 + 10 * max(0.0, -math.sin(t + math.pi)))))
    elif tur == "kos":
        n = n or 8
        for i in range(n):
            t = 2 * math.pi * i / n
            def bacak(f):
                return (38 * math.sin(f) + 4, 15 + 90 * max(0.0, math.cos(f + 0.3)) ** 1.5)
            p = _iskelet(govde_egim=12, bob=0.03 * max(0.0, math.sin(2 * t)),
                         bacak_s=bacak(t), bacak_o=bacak(t + math.pi),
                         kol_s=(-40 * math.sin(t), 85), kol_o=(-40 * math.sin(t + math.pi), 85), yere_bas=False)
            dy = 0.02 - min(p["sag_ayak"][1], p["sol_ayak"][1]) + 0.025 * max(0.0, math.sin(2 * t))
            out.append({k: (None if v is None else (v[0], v[1] + dy)) for k, v in p.items()})
    elif tur == "bekleme":
        n = n or 4
        for i in range(n):
            t = 2 * math.pi * i / n
            out.append(_iskelet(govde_egim=1, bob=-0.006 * (1 - math.cos(t)) / 2,
                                bacak_s=(6, 4), bacak_o=(-6, 4), kol_s=(6 + 2 * math.sin(t), 12), kol_o=(-6 + 2 * math.sin(t), 12)))
    elif tur == "saldir":
        # yakın kol yukarı kalkar (hazırlık) → ileri-aşağı savurur → geri döner
        anim = [(10, 20, 0), (-60, 60, -4), (-150, 30, -8), (-170, 20, -8), (40, 10, 18), (75, 5, 22), (60, 15, 14), (20, 20, 4)]
        n = n or len(anim)
        for i in range(n):
            pa, db, eg = anim[int(i * len(anim) / n)]
            out.append(_iskelet(govde_egim=eg, bacak_s=(22, 8), bacak_o=(-18, 6), kol_s=(pa, db), kol_o=(-25, 40)))
    elif tur == "zipla":
        anim = [(0, 0, 30), (0.0, -0.05, 50), (0.10, 0, 10), (0.16, 0, 35), (0.10, 0, 20), (0.0, -0.05, 50)]
        n = n or len(anim)
        for i in range(n):
            y, bob, diz = anim[int(i * len(anim) / n)]
            p = _iskelet(govde_egim=8, bob=bob, bacak_s=(18 + diz * 0.3, diz), bacak_o=(8 + diz * 0.3, diz),
                         kol_s=(-30 + diz, 30), kol_o=(-40 + diz, 30))
            out.append({k: (None if v is None else (v[0], v[1] + y)) for k, v in p.items()})
    elif tur == "hasar":
        anim = [(0, 0), (-12, 20), (-18, 30), (-8, 15)]
        n = n or len(anim)
        for i in range(n):
            eg, kol = anim[int(i * len(anim) / n)]
            out.append(_iskelet(govde_egim=eg, bas_egim=eg * 0.8, bacak_s=(10, 10), bacak_o=(-10, 8),
                                kol_s=(-kol - 10, 30), kol_o=(-kol - 20, 30), x0=eg * 0.002))
    else:
        raise ValueError(f"bilinmeyen animasyon: {tur}")
    return out


TURLER = ["bekleme", "yuru", "kos", "saldir", "zipla", "hasar"]


def ciz(kare, W=768, H=1024, boy=0.84, x_merkez=0.5, kalin=None):
    """Pozu OpenPose renkleriyle siyah zemine çizer (ControlNet girdisi)."""
    import numpy as np
    from PIL import Image, ImageDraw

    # xinsir/controlnet-openpose-sdxl kalın çizgiyle eğitildi (model kartındaki draw_bodypose): 4 × oran
    if kalin is None:
        m = max(W, H)
        kalin = 4 * (1 if m < 500 else 2 if m < 1000 else 3 if m < 2000 else 4)
    olcek = boy * H
    taban = H * (1 - (1 - boy) / 2)

    def px(p):
        return (W * x_merkez + p[0] * olcek, taban - p[1] * olcek)

    noktalar = [None if kare.get(a) is None else px(kare[a]) for a in ADLAR]
    tuval = np.zeros((H, W, 3), np.float32)
    for i, (a, b) in enumerate(UZUVLAR):
        if noktalar[a] is None or noktalar[b] is None:
            continue
        (x1, y1), (x2, y2) = noktalar[a], noktalar[b]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        L = math.hypot(x2 - x1, y2 - y1) / 2
        ang = math.atan2(y2 - y1, x2 - x1)
        tt = np.linspace(0, 2 * math.pi, 36)
        ex, ey = L * np.cos(tt), kalin * np.sin(tt)
        poly = list(zip(mx + ex * math.cos(ang) - ey * math.sin(ang), my + ex * math.sin(ang) + ey * math.cos(ang)))
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).polygon(poly, fill=255)
        mk = np.array(m, np.float32)[..., None] / 255
        tuval = tuval * (1 - mk) + np.array(RENKLER[i], np.float32) * 0.6 * mk
    im = Image.fromarray(tuval.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for i, p in enumerate(noktalar):
        if p is not None:
            d.ellipse([p[0] - kalin, p[1] - kalin, p[0] + kalin, p[1] + kalin], fill=RENKLER[i])
    return im


if __name__ == "__main__":  # yerel önizleme: python3 modal/pozlar.py → pozlar_onizleme.png
    from PIL import Image

    sat = []
    for tur in TURLER:
        ks = kareler(tur)
        sat.append([ciz(k, 192, 256) for k in ks])
    W = max(len(s) for s in sat) * 192
    out = Image.new("RGB", (W, 256 * len(sat)))
    for j, s in enumerate(sat):
        for i, im in enumerate(s):
            out.paste(im, (i * 192, j * 256))
    out.save("pozlar_onizleme.png")
    print("pozlar_onizleme.png")
