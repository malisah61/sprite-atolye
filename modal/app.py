"""Sprite Atölye — Modal GPU motoru.

SDXL + pixel-art-xl LoRA ile oyun asset'i üretir.
GitHub Actions bu dosyayı `modal deploy modal/app.py` ile kurar.

Uç nokta (POST /generate):
  istek:  {"prompt": str, "seed": int, "n": 1-4, "size": 512-1024,
           "style": "pixel" | "other", "negative": str}
  başlık: X-Sprite-Key: <SPRITE_KEY>
  cevap:  {"images": ["<base64 png>", ...], "seconds": float}
"""
import modal

APP_NAME = "sprite-atolye"
BASE = "stabilityai/stable-diffusion-xl-base-1.0"
VAE = "madebyollin/sdxl-vae-fp16-fix"
PIXEL_LORA = "nerijs/pixel-art-xl"
PIXEL_LORA_FILE = "pixel-art-xl.safetensors"


def download_models():
    from huggingface_hub import snapshot_download, hf_hub_download

    snapshot_download(
        BASE,
        allow_patterns=["*.json", "*.txt", "unet/*.fp16.safetensors", "text_encoder*/*.fp16.safetensors",
                        "tokenizer*/*", "scheduler/*", "model_index.json"],
    )
    snapshot_download(VAE, allow_patterns=["*.json", "*.safetensors"])
    hf_hub_download(PIXEL_LORA, PIXEL_LORA_FILE)


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.1",
        "diffusers==0.31.0",
        "transformers==4.46.3",
        "accelerate==1.1.1",
        "peft==0.13.2",
        "safetensors==0.4.5",
        "huggingface_hub==0.26.2",
        "fastapi[standard]==0.115.5",
        "pillow==11.0.0",
    )
    .run_function(download_models)
)

app = modal.App(APP_NAME, image=image)


@app.cls(
    gpu="T4",
    timeout=600,
    scaledown_window=90,  # 90 sn boşta kalınca kapanır → kredi yemez
    max_containers=1,     # aynı anda tek GPU → bütçe güvende
    secrets=[modal.Secret.from_name("sprite-key")],
)
class Motor:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import AutoencoderKL, DPMSolverMultistepScheduler, StableDiffusionXLPipeline

        vae = AutoencoderKL.from_pretrained(VAE, torch_dtype=torch.float16)
        pipe = StableDiffusionXLPipeline.from_pretrained(
            BASE, vae=vae, torch_dtype=torch.float16, variant="fp16", use_safetensors=True
        )
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config, use_karras_sigmas=True
        )
        pipe.load_lora_weights(PIXEL_LORA, weight_name=PIXEL_LORA_FILE, adapter_name="pixel")
        pipe.to("cuda")
        pipe.enable_vae_slicing()
        self.pipe = pipe

    def _run(self, prompt, negative, seed, n, size, style):
        import base64
        import io
        import time

        import torch

        t0 = time.time()
        self.pipe.set_adapters(["pixel"], adapter_weights=[1.0 if style == "pixel" else 0.0])
        gens = [torch.Generator("cuda").manual_seed(seed + i) for i in range(n)]
        out = self.pipe(
            prompt=prompt,
            negative_prompt=negative,
            num_inference_steps=22,
            guidance_scale=6.0,
            width=size,
            height=size,
            num_images_per_prompt=n,
            generator=gens,
        ).images
        imgs = []
        for im in out:
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            imgs.append(base64.b64encode(buf.getvalue()).decode())
        return {"images": imgs, "seconds": round(time.time() - t0, 2)}

    @modal.asgi_app()
    def web(self):
        import os

        from fastapi import FastAPI, Header, HTTPException
        from fastapi.middleware.cors import CORSMiddleware

        api = FastAPI()
        api.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
        key = os.environ.get("SPRITE_KEY", "")

        @api.get("/")
        def health():
            return {"ok": True, "motor": "sdxl+pixel-art-xl", "gpu": "T4"}

        @api.post("/generate")
        def generate(body: dict, x_sprite_key: str = Header(default="")):
            if key and x_sprite_key != key:
                raise HTTPException(status_code=401, detail="Anahtar yanlış")
            prompt = str(body.get("prompt", ""))[:1500]
            if not prompt:
                raise HTTPException(status_code=400, detail="prompt boş")
            seed = int(body.get("seed", 0)) % (2**31)
            n = max(1, min(4, int(body.get("n", 1))))
            size = max(512, min(1024, int(body.get("size", 1024)) // 64 * 64))
            style = str(body.get("style", "pixel"))
            negative = str(body.get("negative", "text, watermark, blurry, cropped, multiple characters"))[:500]
            return self._run(prompt, negative, seed, n, size, style)

        return api
