"""Hızlı ve tarifi anlayan model DENEMESİ (Z-Image-Turbo; ilk aday FLUX.1-schnell kapılı çıktı) (canlı motora dokunmaz) — 24 Kasım, kullanıcı: "Gemini gibi hızlı ve anlayan bir yol yok mu?"

SDXL tarifi kelime kelime okuyor (CLIP, 77 belirteç): "fil burunlu kedi" → bütün hayvan fil. FLUX.1-schnell (Apache-2.0,
ticari kullanım serbest) tarifi T5 dil modeliyle okur, 4 adımda çizer. 12B model bf16'da L4'e (24 GB) sığmaz →
gövde (transformer) 4-bit NF4 (bitsandbytes) ile ~7 GB; T5 + VAE bf16. Aynı tarifler canlı SDXL motoruyla da çizilir,
yan yana görsel hazırlanır. Çalıştırma: flux_dene.yml (modal run modal/flux_dene.py).
"""
import modal

# 24 Kasım: FLUX.1-schnell HuggingFace'te artık giriş + onay istiyor (401 gated) → HF hesabı/anahtarı olmadan inmiyor.
# Yerine Z-Image-Turbo (Tongyi-MAI, Apache-2.0, 6B, 8-9 adım, tarifi Qwen3 dil modeliyle okur, kapısız).
MODEL = "Tongyi-MAI/Z-Image-Turbo"
FLUX = MODEL  # eski ad (aşağıdaki kod)


def indir():
    from huggingface_hub import model_info, snapshot_download

    bilgi = model_info(MODEL)
    print("[model]", MODEL, "lisans:", (bilgi.card_data or {}).get("license"), "kapı:", bilgi.gated, flush=True)
    snapshot_download(MODEL, ignore_patterns=["*.md", "assets/*", "*.png", "*.jpg", "*.gif", "*.mp4"])


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.6.0", "diffusers==0.36.0", "transformers==4.57.1", "accelerate==1.10.1", "safetensors==0.6.2",
                 "huggingface_hub==0.35.3", "sentencepiece==0.2.0", "protobuf==5.28.3", "pillow==11.0.0", "numpy<2")
    .run_function(indir, timeout=3600)
)
app = modal.App("sprite-atolye-flux-deneme", image=image)


@app.cls(gpu="L4", cpu=4.0, memory=32768, timeout=1800, scaledown_window=30, max_containers=1)
class Flux:
    @modal.enter()
    def yukle(self):
        import time

        import torch
        from diffusers import DiffusionPipeline

        t0 = time.time()
        self.pipe = DiffusionPipeline.from_pretrained(MODEL, torch_dtype=torch.bfloat16)
        print("[model] boru hattı:", type(self.pipe).__name__, flush=True)
        try:
            self.pipe.to("cuda")
            self.offload = False
        except torch.cuda.OutOfMemoryError:  # L4'e sığmazsa parça parça
            torch.cuda.empty_cache()
            self.pipe.enable_model_cpu_offload()
            self.offload = True
        self.yukleme = round(time.time() - t0, 1)
        print("[flux] yüklendi", self.yukleme, "sn,", round(torch.cuda.memory_allocated() / 1e9, 1), "GB", flush=True)

    @modal.method()
    def ciz(self, isler):
        import io
        import time

        import torch

        cik = []
        # ısınma (ilk çağrı derleme/önbellek): süre ölçümüne katılmasın
        self.pipe("warm up", num_inference_steps=1, guidance_scale=0.0, width=512, height=512)
        for ad, prompt, w, h, seed in isler:
            t = time.time()
            im = self.pipe(prompt, num_inference_steps=9, guidance_scale=0.0, width=w, height=h,
                           generator=torch.Generator("cuda").manual_seed(seed)).images[0]
            sn = round(time.time() - t, 1)
            b = io.BytesIO(); im.save(b, format="PNG")
            cik.append((ad, b.getvalue(), sn))
            print(f"[flux] {ad}: {sn} sn", flush=True)
        return {"yukleme": self.yukleme, "offload": self.offload, "gorseller": cik}


BG = "isolated on a plain flat solid light gray background, no shadow, no scenery"
TARIFLER = [
    # (ad, SDXL stili, genişlik, yükseklik, tarif) — sitenin göndereceği biçimde
    ("fil_kedi", "other", 1216, 832,
     "pink-headed cat with torn fur on top, elephant-like nose, wide eyes, sharp teeth, muscular back, tail wagging, confident stance, "
     f"standing on four legs, grayish-green collar with a bead, tiny red ribbon on the left ear, game enemy creature, side view, "
     f"high quality 2D game art, detailed, {BG}"),
    ("fil_kedi_cumle", "other", 1216, 832,
     "A pink cat seen from the side, standing on four legs. Instead of a nose it has a long pink elephant trunk hanging down. "
     "Torn messy fur on its back, wide eyes, sharp teeth, a gray-green collar with a bead, a tiny red ribbon on its left ear. "
     f"2D game enemy, high quality game art, {BG}"),
    ("pixel_zombi", "pixel", 832, 1216,
     f"pixel art, green zombie with torn clothes, solo, one single creature, full body 2D game enemy, crisp pixels, limited color palette, retro game sprite, front view, {BG}"),
    ("cizgi_kadin", "other", 832, 1216,
     f"young woman adventurer with long red hair, green tunic and brown boots, solo, full body 2D game character, 2D cartoon game art, clean bold outlines, flat colors, front view, {BG}"),
    ("hd_aslan", "other", 832, 1216,
     f"lion-headed warrior man in golden armor holding a spear, solo, full body 2D game character, high quality 2D game art, hand painted, detailed shading, front view, {BG}"),
    ("esya_kilic", "other", 1024, 1024,
     f"glowing magic sword with blue runes on the blade, single 2D game item asset, one object, centered, high quality 2D game art, hand painted, {BG}"),
]


@app.local_entrypoint()
def main(seed: int = 42):
    import base64
    import io
    import json
    import os
    import sys
    import time

    from PIL import Image, ImageDraw, ImageFont

    sys.path.insert(0, os.path.dirname(__file__))
    from motor_istemci import cagir

    ozet = open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a")

    def yaz(m):
        print(m, flush=True); ozet.write(f"- {m}\n")

    # 1) FLUX (deneme uygulaması, uzaktan) — canlı motorla paralel değil, sırayla (tek GPU kotası)
    t0 = time.time()
    d = Flux().ciz.remote([(ad, p, w, h, seed) for ad, _s, w, h, p in TARIFLER] + [("fil_kedi_2", TARIFLER[0][4], 1216, 832, seed + 1)])
    yaz(f"Z-Image yükleme {d['yukleme']} sn, parça parça (offload): {d.get('offload')}, toplam {round(time.time() - t0)} sn (soğuk başlangıç dahil)")
    flux = {}
    for ad, png, sn in d["gorseller"]:
        flux[ad] = Image.open(io.BytesIO(png)).convert("RGB"); flux[ad].save(f"flux_{ad}_flux.png")
        yaz(f"Z-Image {ad}: {sn} sn")
    # 2) canlı SDXL motoru, aynı tarif + seed (ekstra kalite/temizlik kapalı: sadece çizim karşılaştırması)
    sdxl = {}
    url = os.environ.get("ESKI_URL", "https://malisah61--sprite-atolye-motor-web.us-east.modal.run")
    for ad, stil, w, h, p in TARIFLER:
        if ad == "fil_kedi_cumle":
            continue
        t = time.time()
        try:
            r = cagir(url, "generate", {"prompt": p, "seed": seed, "n": 1, "width": w, "height": h, "style": stil, "auto": False}, os.environ.get("SPRITE_KEY", ""))
            sdxl[ad] = Image.open(io.BytesIO(base64.b64decode(r["images"][0]))).convert("RGB"); sdxl[ad].save(f"flux_{ad}_sdxl.png")
            yaz(f"SDXL {ad}: GPU {r['seconds']} sn (toplam {round(time.time() - t)} sn)")
        except Exception as e:  # noqa
            yaz(f"SDXL {ad}: olmadı ({e})")
    # 3) yan yana: satır = tarif, sol SDXL (şimdiki), sağ FLUX
    H = 420
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    except Exception:  # noqa
        font = ImageFont.load_default()
    satir = [(ad, [sdxl.get(ad), flux.get(ad)] + ([flux.get("fil_kedi_2"), flux.get("fil_kedi_cumle")] if ad == "fil_kedi" else []))
             for ad, *_ in TARIFLER if ad != "fil_kedi_cumle"]
    W = max(sum(int(c.width * H / c.height) + 10 for c in hc if c) for _, hc in satir) + 20
    tuval = Image.new("RGB", (W, 50 + len(satir) * (H + 40)), (30, 30, 34))
    dr = ImageDraw.Draw(tuval)
    dr.text((10, 12), f"SOL: SDXL (simdiki motor)   SAG: Z-Image-Turbo (9 adim)   seed {seed}", fill=(255, 255, 255), font=font)
    y = 50
    for ad, hc in satir:
        dr.text((10, y + 6), ad + ("  (SDXL | Z-Image | Z-Image seed+1 | Z-Image cumle tarif)" if ad == "fil_kedi" else ""), fill=(255, 220, 120), font=font)
        x = 10
        for c in hc:
            if c is None:
                x += 200; continue
            c = c.resize((int(c.width * H / c.height), H)); tuval.paste(c, (x, y + 34)); x += c.width + 10
        y += H + 40
    tuval.save("flux_yan_yana.png")
    json.dump({"yukleme": d["yukleme"], "sureler": {a: s for a, _p, s in d["gorseller"]}}, open("flux_sureler.json", "w"))
    yaz("Yan yana: flux_yan_yana.png")
