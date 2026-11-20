"""Sprite Atölye — Modal GPU motoru.

SDXL + pixel-art-xl LoRA ile oyun asset'i üretir.
GitHub Actions bu dosyayı `modal deploy modal/app.py` ile kurar.

Uç nokta (POST /generate):
  istek:  {"prompt": str, "seed": int, "n": 1-4, "width"/"height": 512-1216 (veya "size"),
           "style": "pixel" | "other", "negative": str}
  başlık: X-Sprite-Key: <SPRITE_KEY>
           "transparent": bool  → arka planı silinmiş PNG döner
           "auto": bool         → arka plan + gölge + kalıntı temizliği, kırpma (tam çözünürlük)
           "native": bool       → (isteğe bağlı) pixel art'ı gerçek piksel boyutuna indir
  cevap:  {"images": ["<base64 png>", ...], "seconds": float}

           "reference": "<base64>", "ref_scale": 0-1 → referans görsele benzeyen (aynı karakter) üretim
           "tileable": bool     → dikişsiz doku
POST /edit   {"image", "prompt", "strength", "mask"?, "reference"?} → metinle düzenleme / boyayarak (inpaint)
POST /rembg  {"image": "<base64>"} → {"image": "<base64 RGBA png>"}
"""
import modal

APP_NAME = "sprite-atolye"
BASE = "stabilityai/stable-diffusion-xl-base-1.0"
VAE = "madebyollin/sdxl-vae-fp16-fix"
PIXEL_LORA = "nerijs/pixel-art-xl"
PIXEL_LORA_FILE = "pixel-art-xl.safetensors"
IPA_REPO = "h94/IP-Adapter"
IPA_FILE = "ip-adapter_sdxl_vit-h.safetensors"


def download_models():
    from huggingface_hub import snapshot_download, hf_hub_download

    snapshot_download(
        BASE,
        allow_patterns=["*.json", "*.txt", "unet/*.fp16.safetensors", "text_encoder*/*.fp16.safetensors",
                        "tokenizer*/*", "scheduler/*", "model_index.json"],
    )
    snapshot_download(VAE, allow_patterns=["*.json", "*.safetensors"])
    hf_hub_download(PIXEL_LORA, PIXEL_LORA_FILE)
    # IP-Adapter (referans görselle tutarlı karakter) + görüntü kodlayıcı


def download_ipa():
    from huggingface_hub import hf_hub_download, snapshot_download

    hf_hub_download(IPA_REPO, IPA_FILE, subfolder="sdxl_models")
    snapshot_download(IPA_REPO, allow_patterns=["models/image_encoder/*"])


def download_rembg():
    from rembg import new_session

    new_session("isnet-general-use")


def border_bg(rgb):
    """Görselin kenar piksellerinden arka plan rengini (medyan) bulur."""
    import numpy as np

    edge = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return np.median(edge, axis=0)


def defringe(im, passes=12, bg=None):
    """Kenarda kalan arka plan kalıntılarını ve yer gölgesini temizler, alfayı netleştirir.
    bg verilirse sadece arka plan rengine (veya gölgesine) benzeyen kenar pikselleri silinir."""
    import numpy as np
    from PIL import Image

    a = np.array(im.convert("RGBA")).astype(np.int16)
    rgb, al = a[..., :3], a[..., 3]
    al[al < 110] = 0
    al[al >= 110] = 255
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    if bg is not None:
        d = np.sqrt(((rgb - np.asarray(bg)) ** 2).sum(-1))
        lum_bg = float(np.mean(bg))
        lum = rgb.mean(-1)
        # arka plana yakın ya da arka planın koyu (gölge) tonu, düşük doygunluk
        shadow = (sat < 0.12) & (lum < lum_bg) & (lum > lum_bg * 0.45)
        pale = (d < 48) | shadow
    else:
        pale = (sat < 0.22) & (mx > 115)
    for _ in range(passes):
        solid = al > 0
        nb = np.zeros_like(solid)
        nb[1:, :] |= ~solid[:-1, :]
        nb[:-1, :] |= ~solid[1:, :]
        nb[:, 1:] |= ~solid[:, :-1]
        nb[:, :-1] |= ~solid[:, 1:]
        edge = solid & nb & pale
        if not edge.any():
            break
        al[edge] = 0
    a[..., 3] = al
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def drop_debris(im, min_frac=0.03):
    """Ana figüre bağlı olmayan küçük kırıntıları siler (en büyük parçanın %3'ünden küçükler)."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    a = np.array(im.convert("RGBA"))
    lab, n = ndimage.label(a[..., 3] > 0, structure=np.ones((3, 3)))
    if n <= 1:
        return im
    sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= sizes.max() * min_frac
    a[~keep[lab], 3] = 0
    return Image.fromarray(a, "RGBA")


def fill_holes(orig_rgb, cut, bg):
    """Karakterin içinde yanlışlıkla silinen yerleri (beyaz gömlek gibi) geri getirir.
    İçeride kalan şeffaf boşluk arka plan rengine benzemiyorsa geri doldurulur."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    a = np.array(cut.convert("RGBA"))
    opaque = a[..., 3] >= 110
    holes = ndimage.binary_fill_holes(opaque) & ~opaque
    d = np.sqrt(((orig_rgb.astype(np.int32) - np.asarray(bg)) ** 2).sum(-1))
    restore = holes & (d > 40)
    a[restore, :3] = orig_rgb[restore]
    a[restore, 3] = 255
    return Image.fromarray(a, "RGBA")


# ---------- Otomatik temizlik (numpy) ----------
def detect_block(im, kmin=4, kmax=20):
    import numpy as np
    """Pixel art görselin piksel blok boyutunu (ızgara) bulur."""
    a = np.asarray(im.convert("RGBA")).astype(np.int32)
    rgb, al = a[..., :3], a[..., 3]
    best = None
    scores = {}
    for axis in (1, 0):
        d = np.abs(np.diff(rgb, axis=axis)).sum(-1)
        m = (al[:, 1:] > 0) if axis == 1 else (al[1:, :] > 0)
        e = (d > 40) & m
        pos = np.nonzero(e)[axis] + 1
        if len(pos) < 50:
            continue
        for k in range(kmin, kmax + 1):
            h = np.bincount(pos % k, minlength=k)
            # komşu iki ofseti birlikte say (ızgara kayması toleransı)
            hh = h + np.roll(h, -1)
            scores.setdefault(k, []).append(hh.max() / len(pos))
    if not scores:
        return None, {}
    sc = {k: float(np.mean(v)) for k, v in scores.items()}
    for k in range(kmax, kmin - 1, -1):
        if sc.get(k, 0) >= 0.62:
            return k, sc
    return None, sc

def grid_offset(im, k, axis):
    import numpy as np
    a = np.asarray(im.convert("RGBA")).astype(np.int32)
    d = np.abs(np.diff(a[..., :3], axis=axis)).sum(-1)
    m = (a[:, 1:, 3] > 0) if axis == 1 else (a[1:, :, 3] > 0)
    pos = np.nonzero((d > 40) & m)[axis] + 1
    return int(np.bincount(pos % k, minlength=k).argmax()) if len(pos) else 0

def trim(im, pad):
    from PIL import Image
    bb = im.getbbox()
    if not bb:
        return im
    x0, y0, x1, y1 = bb
    out = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    out.paste(im.crop(bb), (pad, pad))
    return out

def to_native_pixels(im, k):
    import numpy as np
    from PIL import Image
    ox, oy = grid_offset(im, k, 1), grid_offset(im, k, 0)
    a = np.asarray(im.convert("RGBA"))
    H, W = a.shape[:2]
    xs = list(range(ox - k if ox else 0, W, k)); ys = list(range(oy - k if oy else 0, H, k))
    out = np.zeros((len(ys), len(xs), 4), np.uint8)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            blk = a[max(0, y):y + k, max(0, x):x + k].reshape(-1, 4)
            if len(blk) == 0:
                continue
            op = blk[blk[:, 3] > 0]
            if len(op) * 2 < len(blk):
                continue
            # merkezdeki piksellere ağırlık: kenar karışımlarını alma
            out[j, i, :3] = np.median(op[:, :3], axis=0)
            out[j, i, 3] = 255
    return Image.fromarray(out, "RGBA")

def auto_clean(im, style, bg=None, native=False):
    """Arka planı silinmiş görseli oyuna hazır hale getirir.
    Varsayılan: tam çözünürlük, sadece kırpma. native=True ise pixel art gerçek piksel boyutuna indirilir."""
    if native and style == "pixel":
        k, _ = detect_block(im)
        if k:
            small = to_native_pixels(im, k)
            return trim(defringe(small, passes=2, bg=bg), 1), k
    return trim(im, 4), None


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
    .pip_install("rembg==2.0.59", "onnxruntime==1.19.2", "scipy")
    .run_function(download_rembg)
    .run_function(download_ipa)
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
        pipe.load_ip_adapter(IPA_REPO, subfolder="sdxl_models", weight_name=IPA_FILE,
                             image_encoder_folder="models/image_encoder")
        pipe.to("cuda")
        pipe.enable_vae_slicing()
        self.pipe = pipe
        from diffusers import StableDiffusionXLImg2ImgPipeline, StableDiffusionXLInpaintPipeline
        from PIL import Image

        self.i2i = StableDiffusionXLImg2ImgPipeline.from_pipe(pipe)
        self.inp = StableDiffusionXLInpaintPipeline.from_pipe(pipe)
        self.blank = Image.new("RGB", (224, 224), (128, 128, 128))
        from rembg import new_session

        self.rb = new_session("isnet-general-use")

    def _cut(self, im, force=False):
        """Yapay zekâ ile arka plan silme (gölge dahil) → RGBA."""
        from rembg import remove

        import numpy as np

        rgb = np.array(im.convert("RGB"))
        bg = border_bg(rgb)
        # kenarlar düz renk değilse (desenli arka plan, çerçeve, sahne) parçalamak yerine tam resmi ver
        w = 24
        edge = np.concatenate([rgb[:w].reshape(-1, 3), rgb[-w:].reshape(-1, 3),
                               rgb[:, :w].reshape(-1, 3), rgb[:, -w:].reshape(-1, 3)]).astype(np.int32)
        busy = float((np.sqrt(((edge - np.median(edge, axis=0)) ** 2).sum(-1)) > 40).mean())
        self.last_plain = busy < 0.15  # kenar şeridinin %15'inden fazlası arka plandan farklıysa: desen/çerçeve/sahne
        if not self.last_plain and not force:
            self.last_bg = None
            return im.convert("RGBA")
        raw = remove(im.convert("RGB"), session=self.rb, post_process_mask=True)
        out = fill_holes(rgb, raw, bg)
        self.last_bg = bg
        final = drop_debris(defringe(out, bg=bg))
        # güvenlik: temizlik figürün büyük kısmını yediyse (arka plan rengi karaktere çok benziyorsa) ham kesime dön
        area = lambda x: int((np.array(x)[..., 3] > 0).sum())
        if area(final) < 0.6 * max(1, area(out)):
            return drop_debris(out)
        return final

    def _tile(self, on):
        """Dikişsiz (seamless) doku için evrişim katmanlarını dairesel dolguya al."""
        import torch

        for model in (self.pipe.unet, self.pipe.vae):
            for m in model.modules():
                if isinstance(m, torch.nn.Conv2d):
                    m.padding_mode = "circular" if on else "zeros"

    def _ref(self, b64):
        import base64
        import io

        from PIL import Image

        if not b64:
            return None
        im = Image.open(io.BytesIO(base64.b64decode(str(b64).split(",")[-1])))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bgim = Image.new("RGBA", im.size, (128, 128, 128, 255))
            bgim.alpha_composite(im)
            im = bgim
        return im.convert("RGB")

    def _common(self, style, ref_img, ref_scale):
        self.pipe.set_adapters(["pixel"], adapter_weights=[1.0 if style == "pixel" else 0.0])
        self.pipe.set_ip_adapter_scale(float(ref_scale) if ref_img is not None else 0.0)
        return ref_img if ref_img is not None else self.blank

    def _post(self, out, transparent, auto, style, native, force=False):
        import base64
        import io

        imgs, grids, plains = [], [], []
        for im in out:
            if transparent or auto:
                im = self._cut(im, force)
                plains.append(getattr(self, "last_plain", True))
            if auto:
                im, k = auto_clean(im, style, getattr(self, "last_bg", None), native)
                grids.append(k)
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            imgs.append(base64.b64encode(buf.getvalue()).decode())
        return imgs, grids, plains

    def _edit(self, image, mask, prompt, negative, seed, strength, style, ref_img, ref_scale, auto):
        import time

        import torch
        from PIL import Image

        t0 = time.time()
        w, h = image.size
        s = 1024 / max(w, h)
        W, H = max(512, int(w * s) // 64 * 64), max(512, int(h * s) // 64 * 64)
        image = image.resize((W, H), Image.LANCZOS)
        ipa = self._common(style, ref_img, ref_scale)
        g = torch.Generator("cuda").manual_seed(seed)
        kw = dict(prompt=prompt, negative_prompt=negative, image=image, strength=float(strength),
                  num_inference_steps=30, guidance_scale=6.0, generator=g, ip_adapter_image=ipa)
        if mask is not None:
            mask = mask.convert("L").resize((W, H), Image.NEAREST)
            out = self.inp(mask_image=mask, width=W, height=H, **kw).images
        else:
            out = self.i2i(**kw).images
        # düzenlenen görsel zaten tek figür: arka plan desenli görünse bile kesmeyi zorla
        imgs, grids, plains = self._post(out, auto, auto, style, False, force=True)
        return {"images": imgs, "plain": plains, "seconds": round(time.time() - t0, 2)}

    def _run(self, prompt, negative, seed, n, width, height, style, transparent=False, auto=False, native=False,
             ref_img=None, ref_scale=0.6, tileable=False):
        import base64
        import io
        import time

        import torch

        t0 = time.time()
        ipa = self._common(style, ref_img, ref_scale)
        gens = [torch.Generator("cuda").manual_seed(seed + i) for i in range(n)]
        if tileable:
            self._tile(True)
        try:
            out = self.pipe(
                prompt=prompt,
                negative_prompt=negative,
                num_inference_steps=22,
                guidance_scale=6.0,
                width=width,
                height=height,
                num_images_per_prompt=n,
                generator=gens,
                ip_adapter_image=ipa,
            ).images
        finally:
            if tileable:
                self._tile(False)
        if tileable:  # dokular kesilmez, temizlenmez
            transparent = auto = False
        imgs, grids, plains = self._post(out, transparent, auto, style, native)
        return {"images": imgs, "grid": grids, "plain": plains, "seconds": round(time.time() - t0, 2)}

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
            return {"ok": True, "motor": "sdxl+pixel-art-xl+ip-adapter", "gpu": "T4",
                    "ozellikler": ["generate", "reference", "tileable", "edit", "inpaint", "rembg"]}

        @api.post("/generate")
        def generate(body: dict, x_sprite_key: str = Header(default="")):
            if key and x_sprite_key != key:
                raise HTTPException(status_code=401, detail="Anahtar yanlış")
            prompt = str(body.get("prompt", ""))[:1500]
            if not prompt:
                raise HTTPException(status_code=400, detail="prompt boş")
            seed = int(body.get("seed", 0)) % (2**31)
            n = max(1, min(4, int(body.get("n", 1))))
            size = int(body.get("size", 1024))
            clamp = lambda v: max(512, min(1216, int(v) // 64 * 64))
            width = clamp(body.get("width", size))
            height = clamp(body.get("height", size))
            style = str(body.get("style", "pixel"))
            negative = str(body.get("negative", "text, watermark, blurry, cropped, multiple characters, character sheet, multiple views, duplicate, turnaround, ground shadow, cast shadow, drop shadow, shadow under feet, frame, border, card frame, ornamental background, patterned background, wallpaper, scenery, landscape"))[:500]
            transparent = bool(body.get("transparent", False))
            auto = bool(body.get("auto", False))
            native = bool(body.get("native", False))
            ref_img = self._ref(body.get("reference"))
            ref_scale = max(0.0, min(1.0, float(body.get("ref_scale", 0.6))))
            tileable = bool(body.get("tileable", False))
            return self._run(prompt, negative, seed, n, width, height, style, transparent, auto, native,
                             ref_img, ref_scale, tileable)

        @api.post("/edit")
        def edit(body: dict, x_sprite_key: str = Header(default="")):
            """Var olan görseli metinle düzenle (img2img); mask verilirse sadece boyanan yeri yeniden çiz (inpaint)."""
            if key and x_sprite_key != key:
                raise HTTPException(status_code=401, detail="Anahtar yanlış")
            image = self._ref(body.get("image"))
            if image is None:
                raise HTTPException(status_code=400, detail="image boş")
            mask = None
            if body.get("mask"):
                import base64
                import io

                from PIL import Image

                mask = Image.open(io.BytesIO(base64.b64decode(str(body["mask"]).split(",")[-1])))
                if mask.mode == "RGBA":  # boyanan (opak) yerler beyaz = yeniden çiz
                    mask = mask.split()[-1]
            prompt = str(body.get("prompt", ""))[:1500]
            negative = str(body.get("negative", "text, watermark, blurry, cropped, multiple characters, frame, border"))[:500]
            strength = max(0.15, min(1.0, float(body.get("strength", 0.6 if mask is None else 0.95))))
            return self._edit(image, mask, prompt, negative, int(body.get("seed", 0)) % (2**31), strength,
                              str(body.get("style", "other")), self._ref(body.get("reference")),
                              max(0.0, min(1.0, float(body.get("ref_scale", 0.5)))), bool(body.get("auto", True)))

        @api.post("/rembg")
        def rembg(body: dict, x_sprite_key: str = Header(default="")):
            import base64
            import io
            import time

            from PIL import Image

            if key and x_sprite_key != key:
                raise HTTPException(status_code=401, detail="Anahtar yanlış")
            t0 = time.time()
            raw = base64.b64decode(str(body.get("image", "")).split(",")[-1])
            im = Image.open(io.BytesIO(raw))
            im.thumbnail((2048, 2048))
            out = self._cut(im)
            k = None
            if body.get("auto", True):
                out, k = auto_clean(out, "pixel", getattr(self, "last_bg", None), bool(body.get("native", False)))
            buf = io.BytesIO()
            out.save(buf, format="PNG")
            return {"image": base64.b64encode(buf.getvalue()).decode(), "grid": k, "seconds": round(time.time() - t0, 2)}

        return api
