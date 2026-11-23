"""Yapay zekâ animasyonu DENEMESİ (canlı motora dokunmaz): OpenPose ControlNet + IP-Adapter ile kare kare animasyon.

Model: xinsir/controlnet-openpose-sdxl-1.0 (Apache-2.0, ticari kullanım serbest; thibaud'unki "other"/OpenPose lisansı → elendi).
Pozlar: modal/pozlar.py (kodla, yandan).
İki yöntem karşılaştırılır:
  A) bağımsız: her kare = poz ControlNet + referans (IP-Adapter) + aynı seed
  B) yan yana: 2 kat genişlikte tuval, solda referans görsel (sabit), sağda yeni kare (inpaint) → model aynı karakteri
     "kopyalar" (aynı resim içinde dikkat paylaşımı → daha tutarlı)
Çalıştırma: modal run modal/anim_dene.py --tarif "..." --anim yuru --yontem AB
Çıktı: anim_*.png (kareler, sayfa) + anim_*.gif
"""
from pathlib import Path

import modal

BASE = "Lykon/dreamshaper-xl-1-0"
VAE = "madebyollin/sdxl-vae-fp16-fix"
IPA_REPO = "h94/IP-Adapter"
IPA_FILE = "ip-adapter_sdxl_vit-h.safetensors"
CN = "xinsir/controlnet-openpose-sdxl-1.0"
STYLE_LORAS = {"cartoon": ("issaccyj/lora-sdxl-cartoonillustration", "pytorch_lora_weights.safetensors", 0.8, "in szn style")}


def indir():
    from huggingface_hub import hf_hub_download, snapshot_download

    snapshot_download(BASE, allow_patterns=["*.json", "*.txt", "unet/*.fp16.safetensors", "text_encoder*/*.fp16.safetensors",
                                            "tokenizer*/*", "scheduler/*", "model_index.json"])
    snapshot_download(VAE, allow_patterns=["*.json", "*.safetensors"])
    hf_hub_download(IPA_REPO, IPA_FILE, subfolder="sdxl_models")
    snapshot_download(IPA_REPO, allow_patterns=["models/image_encoder/*"])
    snapshot_download(CN, allow_patterns=["config.json", "diffusion_pytorch_model.safetensors"])
    for repo, dosya, *_ in STYLE_LORAS.values():
        hf_hub_download(repo, dosya)


def indir_rembg():
    from rembg import new_session

    new_session("birefnet-general-lite")


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.4.1", "diffusers==0.31.0", "transformers==4.46.3", "accelerate==1.1.1", "peft==0.13.2",
                 "safetensors==0.4.5", "huggingface_hub==0.26.2", "pillow==11.0.0", "numpy<2")
    .run_function(indir, timeout=3600)
    .pip_install("rembg==2.0.59", "onnxruntime==1.19.2", "scipy")
    .run_function(indir_rembg)
    .add_local_file(Path(__file__).parent / "pozlar.py", "/root/pozlar.py")
)
app = modal.App("sprite-atolye-anim-deneme", image=image)


# T4 (15 GB) yetmedi: SDXL + ControlNet + IP-Adapter ≈ 12,5 GB, 1536×1024 VAE çözümünde bellek taştı (23 Kasım) → L4 (24 GB)
@app.cls(gpu="L4", cpu=4.0, timeout=1800, scaledown_window=30, max_containers=1)
class Anim:
    @modal.enter()
    def yukle(self):
        import torch
        from diffusers import (AutoencoderKL, ControlNetModel, DPMSolverMultistepScheduler,
                               StableDiffusionXLControlNetInpaintPipeline, StableDiffusionXLControlNetPipeline)

        vae = AutoencoderKL.from_pretrained(VAE, torch_dtype=torch.float16)
        cn = ControlNetModel.from_pretrained(CN, torch_dtype=torch.float16)
        pipe = StableDiffusionXLControlNetPipeline.from_pretrained(BASE, vae=vae, controlnet=cn, torch_dtype=torch.float16,
                                                                   variant="fp16", use_safetensors=True)
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="dpmsolver++", solver_type="midpoint",
            final_sigmas_type="zero", timestep_spacing="leading", steps_offset=1)
        for ad, (repo, dosya, w, _t) in STYLE_LORAS.items():
            pipe.load_lora_weights(repo, weight_name=dosya, adapter_name=ad)
        pipe.load_ip_adapter(IPA_REPO, subfolder="sdxl_models", weight_name=IPA_FILE, image_encoder_folder="models/image_encoder")
        pipe.to("cuda")
        pipe.enable_vae_slicing()
        pipe.enable_vae_tiling()
        self.pipe = pipe
        self.inp = StableDiffusionXLControlNetInpaintPipeline.from_pipe(pipe)
        from rembg import new_session

        self.rb = new_session("birefnet-general-lite")
        print("[anim] yüklendi", torch.cuda.memory_allocated() / 1e9, "GB", flush=True)

    @modal.method()
    def calis(self, tarif, anim="yuru", yontem="AB", seed=7, lora="", n=0, ref_png=None):
        import io
        import time

        import torch
        from PIL import Image

        import pozlar

        neg = ("text, watermark, blurry, cropped, multiple characters, duplicate, frame, border, scenery, landscape, "
               "ground shadow, cast shadow, deformed, extra limbs, extra arms, extra legs, bad anatomy")
        if lora in STYLE_LORAS:
            self.pipe.set_adapters([lora], adapter_weights=[STYLE_LORAS[lora][2]])
            tarif = f"{tarif}, {STYLE_LORAS[lora][3]}"
        else:
            self.pipe.disable_lora()
        W, H = 768, 1024
        tam = f"{tarif}, solo, one single character, full body, side view, facing right, profile, isolated on a plain flat solid light gray background"
        sonuc, sure = {}, {}
        g = lambda: torch.Generator("cuda").manual_seed(seed)
        # 1) referans karakter: bekleme pozunda (yandan) — kullanıcı görseli verilmişse o
        dur = pozlar.ciz(pozlar.kareler("bekleme")[0], W, H)
        t0 = time.time()
        if ref_png:
            ref = Image.open(io.BytesIO(ref_png)).convert("RGBA")
            bg = Image.new("RGBA", ref.size, (200, 200, 200, 255)); bg.alpha_composite(ref)
            ref = bg.convert("RGB")
            ref.thumbnail((W, H)); c = Image.new("RGB", (W, H), (200, 200, 200)); c.paste(ref, ((W - ref.width) // 2, H - ref.height)); ref = c
        else:
            self.pipe.set_ip_adapter_scale(0.0)
            ref = self.pipe(prompt=tam, negative_prompt=neg, image=dur, num_inference_steps=25, guidance_scale=6.0,
                            width=W, height=H, generator=g(), ip_adapter_image=Image.new("RGB", (224, 224), (128, 128, 128)),
                            controlnet_conditioning_scale=0.9).images[0]
        sure["referans"] = round(time.time() - t0, 1)
        sonuc["ref"] = ref
        poz = pozlar.kareler(anim, n or None)
        sonuc["poz"] = [pozlar.ciz(p, W, H) for p in poz]
        if "A" in yontem:
            t0 = time.time()
            self.pipe.set_ip_adapter_scale(0.7)
            sonuc["A"] = [self.pipe(prompt=tam, negative_prompt=neg, image=pz, num_inference_steps=25, guidance_scale=6.0,
                                    width=W, height=H, generator=g(), ip_adapter_image=ref,
                                    controlnet_conditioning_scale=1.0).images[0] for pz in sonuc["poz"]]
            sure["A"] = round(time.time() - t0, 1)
        if "B" in yontem:
            t0 = time.time()
            self.inp.set_ip_adapter_scale(0.5)
            iki = (f"two side-by-side pictures of the exact same character, identical outfit and colors, {tarif}, "
                   "full body, side view, facing right, isolated on a plain flat solid light gray background")
            maske = Image.new("L", (2 * W, H), 0); maske.paste(255, (W, 0, 2 * W, H))
            kareler = []
            for pz in sonuc["poz"]:
                tuval = Image.new("RGB", (2 * W, H), (200, 200, 200)); tuval.paste(ref, (0, 0))
                kontrol = Image.new("RGB", (2 * W, H)); kontrol.paste(dur, (0, 0)); kontrol.paste(pz, (W, 0))
                out = self.inp(prompt=iki, negative_prompt=neg.replace("multiple characters, duplicate, ", ""), image=tuval,
                               mask_image=maske, control_image=kontrol, width=2 * W, height=H, strength=1.0,
                               num_inference_steps=25, guidance_scale=6.0, generator=g(), ip_adapter_image=ref,
                               controlnet_conditioning_scale=1.0).images[0]
                kareler.append(out.crop((W, 0, 2 * W, H)))
            sonuc["B"] = kareler
            sure["B"] = round(time.time() - t0, 1)
        # arka plan sil (karşılaştırma için)
        from rembg import remove

        def png(im):
            b = io.BytesIO(); im.save(b, format="PNG"); return b.getvalue()

        cik = {"ref": png(ref), "poz": [png(p) for p in sonuc["poz"]], "sure": sure}
        for k in ("A", "B"):
            if k in sonuc:
                cik[k] = [png(remove(im, session=self.rb, post_process_mask=True)) for im in sonuc[k]]
        print("[anim] süreler", sure, flush=True)
        return cik


@app.local_entrypoint()
def main(tarif: str = "WW2 British commando soldier, adult man, green beret, dark green denison camouflage smock, khaki trousers, black boots, holding a rifle, high quality 2D game art, hand painted, detailed shading",
         anim: str = "yuru", yontem: str = "AB", seed: int = 7, lora: str = "", n: int = 0, ref: str = "", etiket: str = "anim"):
    import io

    from PIL import Image

    ref_png = open(ref, "rb").read() if ref and Path(ref).exists() else None
    d = Anim().calis.remote(tarif, anim, yontem, seed, lora, n, ref_png)
    print("süreler:", d["sure"])
    Image.open(io.BytesIO(d["ref"])).save(f"{etiket}_referans.png")
    satirlar = []
    pozlar_im = [Image.open(io.BytesIO(b)) for b in d["poz"]]
    satirlar.append(("poz", pozlar_im))
    for k in ("A", "B"):
        if k not in d:
            continue
        ims = [Image.open(io.BytesIO(b)).convert("RGBA") for b in d[k]]
        for i, im in enumerate(ims):
            im.save(f"{etiket}_{k}_{i}.png")
        # GIF (gri zemin)
        kare = []
        for im in ims:
            bg = Image.new("RGBA", im.size, (90, 90, 90, 255)); bg.alpha_composite(im)
            kare.append(bg.convert("RGB").resize((im.width // 2, im.height // 2)))
        kare[0].save(f"{etiket}_{k}.gif", save_all=True, append_images=kare[1:], duration=110, loop=0)
        satirlar.append((k, ims))
    # sayfa: her satır bir yöntem
    w, h = 192, 256
    n = max(len(s) for _, s in satirlar)
    sayfa = Image.new("RGB", (w * (n + 1), h * len(satirlar)), (90, 90, 90))
    ref_k = Image.open(io.BytesIO(d["ref"])).convert("RGB").resize((w, h))
    for j, (k, ims) in enumerate(satirlar):
        if j:
            sayfa.paste(ref_k, (0, j * h))
        for i, im in enumerate(ims):
            im = im.convert("RGBA").resize((w, h))
            bg = Image.new("RGBA", (w, h), (90, 90, 90, 255)); bg.alpha_composite(im)
            sayfa.paste(bg.convert("RGB"), ((i + 1) * w, j * h))
    sayfa.save(f"{etiket}_sayfa.png")
    print("kaydedildi:", f"{etiket}_sayfa.png")
