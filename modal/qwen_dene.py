"""Qwen-Image + Lightning DENEMESİ (canlı motora dokunmaz) — 24 Kasım, kullanıcı: "Gemini gibi hızlı ve anlayan".

Qwen-Image (Apache-2.0, 20B): açık modeller içinde tarifi en iyi anlayanlardan (metin kodlayıcı Qwen2.5-VL 7B).
Lightning LoRA (lightx2v/Qwen-Image-Lightning, Apache-2.0): 8 adımda çizim.
Kart: L40S (48 GB). bf16 gövde (~41 GB) + metin kodlayıcı (~16 GB) sığmaz → gövde float8 (torchao, yalnız ağırlık;
L40S fp8 destekler); olmazsa bf16 + parça parça (cpu offload) — hangisi kullanıldığı kayda yazılır.
Aynı tarifler canlı SDXL motoruyla (sitenin varsayılan ayarlarıyla) da çizilir; süre ve maliyet yan yana.
Çalıştırma: qwen_dene.yml (modal run modal/qwen_dene.py)
"""
import math

import modal

MODEL = "Qwen/Qwen-Image"
LORA = "lightx2v/Qwen-Image-Lightning"
LORA_DOSYA = "Qwen-Image-Lightning-8steps-V1.1.safetensors"
GPU = "L40S"
SAAT_UCRET = {"L40S": 1.95, "T4": 0.59}  # $/saat, Modal liste fiyatı (yaklaşık; değişmiş olabilir)


def indir():
    from huggingface_hub import list_repo_files, model_info, snapshot_download

    for m in (MODEL, LORA):
        b = model_info(m)
        print("[model]", m, "lisans:", (b.card_data or {}).get("license"), "kapı:", b.gated, flush=True)
    print("[lora dosyaları]", [f for f in list_repo_files(LORA) if f.endswith(".safetensors")], flush=True)
    snapshot_download(MODEL, ignore_patterns=["*.md", "assets/*", "*.png", "*.jpg", "*.gif", "*.mp4"])
    snapshot_download(LORA, allow_patterns=["*8steps*.safetensors", "*.json"])


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.6.0", "torchao==0.10.0", "diffusers==0.35.1", "transformers==4.56.2", "accelerate==1.10.1",
                 "safetensors==0.6.2", "huggingface_hub==0.35.3", "peft==0.17.1", "sentencepiece==0.2.0",
                 "protobuf==5.28.3", "pillow==11.0.0", "numpy<2")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "0"})
    .run_function(indir, timeout=5400)
)
app = modal.App("sprite-atolye-qwen-deneme", image=image)


@app.cls(gpu=GPU, cpu=8.0, memory=98304, timeout=2400, scaledown_window=30, max_containers=1)
class Qwen:
    @modal.enter()
    def yukle(self):
        import os
        import time

        import torch
        from diffusers import DiffusionPipeline, FlowMatchEulerDiscreteScheduler

        import glob

        from huggingface_hub import snapshot_download

        t0 = time.time()
        yol = snapshot_download(LORA, allow_patterns=["*8steps*.safetensors"], local_files_only=True)
        adaylar = sorted(os.path.basename(f) for f in glob.glob(f"{yol}/**/*8steps*.safetensors", recursive=True))
        temiz = [a for a in adaylar if "fp8" not in a.lower() and "edit" not in a.lower()] or adaylar
        lora_dosya = LORA_DOSYA if LORA_DOSYA in temiz else temiz[-1]
        print("[qwen] Lightning dosyası:", lora_dosya, "adaylar:", adaylar, flush=True)
        # Lightning'in model kartındaki zamanlayıcı ayarı
        sch = FlowMatchEulerDiscreteScheduler.from_config({
            "base_image_seq_len": 256, "base_shift": math.log(3), "invert_sigmas": False, "max_image_seq_len": 8192,
            "max_shift": math.log(3), "num_train_timesteps": 1000, "shift": 1.0, "shift_terminal": None,
            "stochastic_sampling": False, "time_shift_type": "exponential", "use_beta_sigmas": False,
            "use_dynamic_shifting": True, "use_exponential_sigmas": False, "use_karras_sigmas": False})
        self.kip = "?"
        try:
            from diffusers import QwenImageTransformer2DModel, TorchAoConfig

            tr = QwenImageTransformer2DModel.from_pretrained(MODEL, subfolder="transformer", torch_dtype=torch.bfloat16,
                                                             quantization_config=TorchAoConfig("float8wo_e4m3"))
            pipe = DiffusionPipeline.from_pretrained(MODEL, transformer=tr, scheduler=sch, torch_dtype=torch.bfloat16)
            pipe.load_lora_weights(LORA, weight_name=lora_dosya)
            pipe.to("cuda")
            self.kip = "float8 gövde, hepsi GPU'da"
        except Exception as e:  # noqa
            print("[qwen] float8 olmadı:", type(e).__name__, str(e)[:300], flush=True)
            torch.cuda.empty_cache()
            pipe = DiffusionPipeline.from_pretrained(MODEL, scheduler=sch, torch_dtype=torch.bfloat16)
            pipe.load_lora_weights(LORA, weight_name=lora_dosya)
            pipe.enable_model_cpu_offload()
            self.kip = "bf16 + parça parça (cpu offload)"
        self.pipe = pipe
        self.yukleme = round(time.time() - t0, 1)
        print(f"[qwen] yüklendi {self.yukleme} sn, kip: {self.kip}, GPU {round(torch.cuda.memory_allocated() / 1e9, 1)} GB", flush=True)

    @modal.method()
    def ciz(self, isler):
        import io
        import time

        import torch

        t_ac = time.time()
        self.pipe("warm up", negative_prompt=" ", num_inference_steps=2, true_cfg_scale=1.0, width=512, height=512)
        cik = []
        for ad, prompt, w, h, seed in isler:
            t = time.time()
            im = self.pipe(prompt, negative_prompt=" ", num_inference_steps=8, true_cfg_scale=1.0, width=w, height=h,
                           generator=torch.Generator("cuda").manual_seed(seed)).images[0]
            sn = round(time.time() - t, 1)
            b = io.BytesIO(); im.save(b, format="PNG")
            cik.append((ad, b.getvalue(), sn))
            print(f"[qwen] {ad}: {sn} sn", flush=True)
        return {"yukleme": self.yukleme, "kip": self.kip, "isinma": round(time.time() - t_ac - sum(c[2] for c in cik), 1), "gorseller": cik}


BG = "isolated on a plain flat solid light gray background, no shadow, no scenery"
# (ad, SDXL stili, genişlik, yükseklik, tarif — sitenin yorumlayıcısının üreteceği biçimde, SDXL için hibrit bilgisi)
TARIFLER = [
    ("vampir_orumcek", "other", 1216, 832,
     "spider-bodied creature with a cat head, vampire, not humanoid, eight long black hairy spider legs, no arms, round spider abdomen, "
     "cat head with long vampire fangs and glowing red eyes, pale gray fur, small black bat-wing collar, game enemy creature, side view, "
     f"high quality 2D game art, detailed, {BG}",
     {"parts": [{"name": "head", "want": "cat head with long vampire fangs and glowing red eyes"}], "base": "spider", "absent": ["arms"]}),
    ("fil_kedi", "other", 1216, 832,
     "pink-headed cat with torn fur on top, elephant-like nose, wide eyes, sharp teeth, muscular back, tail wagging, confident stance, "
     f"standing on four legs, grayish-green collar with a bead, tiny red ribbon on the left ear, game enemy creature, side view, "
     f"high quality 2D game art, detailed, {BG}",
     {"parts": [{"name": "nose", "want": "long pink elephant trunk"}], "base": "cat"}),
    ("pixel_zombi", "pixel", 832, 1216,
     f"pixel art, green zombie with torn clothes, solo, one single creature, full body 2D game enemy, crisp pixels, limited color palette, retro game sprite, front view, {BG}", {}),
    ("cizgi_kadin", "other", 832, 1216,
     f"young woman adventurer with long red hair, green tunic and brown boots, solo, full body 2D game character, 2D cartoon game art, clean bold outlines, flat colors, front view, {BG}", {}),
    ("hd_aslan", "other", 832, 1216,
     f"lion-headed warrior man in golden armor holding a spear, solo, full body 2D game character, high quality 2D game art, hand painted, detailed shading, front view, {BG}", {}),
    ("esya_kilic", "other", 1024, 1024,
     f"glowing magic sword with blue runes on the blade, single 2D game item asset, one object, centered, high quality 2D game art, hand painted, {BG}", {}),
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
    rapor = {"qwen": {}, "sdxl": {}}

    def yaz(m):
        print(m, flush=True); ozet.write(f"- {m}\n")

    isler = [(ad, p, w, h, seed) for ad, _s, w, h, p, _e in TARIFLER]
    isler += [(f"{ad}_2", p, w, h, seed + 1) for ad, _s, w, h, p, _e in TARIFLER[:2]]
    t0 = time.time()
    d = Qwen().ciz.remote(isler)
    toplam_q = round(time.time() - t0)
    yaz(f"Qwen-Image ({GPU}, {d['kip']}): model yükleme {d['yukleme']} sn, ısınma {d['isinma']} sn, toplam {toplam_q} sn (kurulum/soğuk başlangıç dahil)")
    qw = {}
    for ad, png, sn in d["gorseller"]:
        qw[ad] = Image.open(io.BytesIO(png)).convert("RGB"); qw[ad].save(f"qwen_{ad}_qwen.png")
        maliyet = sn * SAAT_UCRET[GPU] / 3600
        rapor["qwen"][ad] = {"sn": sn, "dolar": round(maliyet, 4)}
        yaz(f"Qwen {ad}: {sn} sn ≈ {maliyet:.4f} $")
    # canlı SDXL motoru — sitenin varsayılanlarıyla (temizlik + ekstra kalite + yüz düzeltme + hibrit parçalar)
    url = os.environ.get("ESKI_URL", "https://malisah61--sprite-atolye-motor-web.us-east.modal.run")
    sd = {}
    for ad, stil, w, h, p, ek in TARIFLER:
        for k, s in ((ad, seed), (f"{ad}_2", seed + 1)):
            if k.endswith("_2") and ad not in ("vampir_orumcek", "fil_kedi"):
                continue
            govde = {"prompt": p, "seed": s, "n": 1, "width": w, "height": h, "style": stil, "auto": True,
                     "hires": stil != "pixel", "yuz": stil != "pixel" and ad != "esya_kilic", **ek}
            t = time.time()
            try:
                r = cagir(url, "generate", govde, os.environ.get("SPRITE_KEY", ""))
                im = Image.open(io.BytesIO(base64.b64decode(r["images"][0]))).convert("RGBA")
                bg = Image.new("RGBA", im.size, (200, 200, 200, 255)); bg.alpha_composite(im); sd[k] = bg.convert("RGB")
                sd[k].save(f"qwen_{k}_sdxl.png")
                tt = round(time.time() - t)
                maliyet = r["seconds"] * SAAT_UCRET["T4"] / 3600
                rapor["sdxl"][k] = {"gpu_sn": r["seconds"], "bekleme_dahil_sn": tt, "dolar": round(maliyet, 4)}
                yaz(f"SDXL {k}: GPU {r['seconds']} sn ≈ {maliyet:.4f} $ (bekleme dahil {tt} sn)")
            except Exception as e:  # noqa
                yaz(f"SDXL {k}: olmadı ({e})")
    # yan yana: satır = tarif; SDXL | Qwen (+ ikinci seed)
    H = 400
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except Exception:  # noqa
        font = ImageFont.load_default()
    satir = []
    for ad, *_ in TARIFLER:
        hc = [("SDXL", sd.get(ad), rapor["sdxl"].get(ad, {}).get("gpu_sn")), ("Qwen", qw.get(ad), rapor["qwen"].get(ad, {}).get("sn"))]
        if ad in ("vampir_orumcek", "fil_kedi"):
            hc += [("SDXL seed+1", sd.get(ad + "_2"), rapor["sdxl"].get(ad + "_2", {}).get("gpu_sn")),
                   ("Qwen seed+1", qw.get(ad + "_2"), rapor["qwen"].get(ad + "_2", {}).get("sn"))]
        satir.append((ad, hc))
    W = max(sum(int((c.width if c else 600) * H / (c.height if c else 400)) + 10 for _, c, _s in hc) for _, hc in satir) + 20
    tuval = Image.new("RGB", (W, 50 + len(satir) * (H + 64)), (30, 30, 34))
    dr = ImageDraw.Draw(tuval)
    dr.text((10, 12), f"SDXL (simdiki motor, T4, site ayarlari) vs Qwen-Image + Lightning (8 adim, {GPU})   seed {seed}", fill=(255, 255, 255), font=font)
    y = 50
    for ad, hc in satir:
        dr.text((10, y + 4), ad, fill=(255, 220, 120), font=font)
        x = 10
        for et, c, s in hc:
            if c is None:
                x += 200; continue
            c = c.resize((int(c.width * H / c.height), H)); tuval.paste(c, (x, y + 30))
            dr.text((x + 4, y + 34 + H), f"{et}: {s} sn", fill=(200, 230, 255), font=font)
            x += c.width + 10
        y += H + 64
    tuval.save("qwen_yan_yana.png")
    rapor["qwen_genel"] = {"yukleme_sn": d["yukleme"], "kip": d["kip"], "toplam_sn": toplam_q}
    json.dump(rapor, open("qwen_rapor.json", "w"), ensure_ascii=False, indent=1)
    yaz("Yan yana: qwen_yan_yana.png")
