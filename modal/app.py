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
           "parts": [{"name":"head","want":"monkey head..."}], "base": "snake" → otomatik parça kontrolü ve düzeltme
           "lora": "cartoon"|"chibi"|"dark", "lora_weight": 0-2 → stile özel LoRA (tetik kelimesi otomatik eklenir)
           "yuz": bool → yüz düzeltme (0d): yüz bulunur, 1024'e büyütülüp img2img 0.4 ile yeniden çizilir; cevapta "yuz"
           "hires": bool → iki aşamalı üretim (hi-res fix): 1.5x büyüt + img2img (0.35), pixel/doku hariç; cevapta "hires"
           "dersler": bool (varsayılan true) → DERSLER kuralları; "iki_asama": bool → pixel'de taslak+referans
           cevapta "dersler": [uygulanan ders adları], "iki_asama": taslak kullanıldı mı,
           "puan": [0-1] her görselin tarife uyumu (n>1 ise en iyisi başta)
POST /edit   {"image", "prompt", "strength", "mask"?, "reference"?} → metinle düzenleme / boyayarak (inpaint)
POST /rembg  {"image": "<base64>"} → {"image": "<base64 RGBA png>"}
"""
from pathlib import Path

import modal

APP_NAME = "sprite-atolye"
# DreamShaper XL 1.0 (SDXL ince ayarı, lisans openrail++ — ticari kullanım serbest). 20 Kasım karşılaştırmasında
# SDXL base'e göre pixel ve HD'de belirgin daha detaylı. Eskiye dönmek için: "stabilityai/stable-diffusion-xl-base-1.0"
BASE = "Lykon/dreamshaper-xl-1-0"
VAE = "madebyollin/sdxl-vae-fp16-fix"
PIXEL_LORA = "nerijs/pixel-art-xl"
PIXEL_LORA_FILE = "pixel-art-xl.safetensors"
# Stile özel LoRA'lar (hepsi SDXL için, lisansları ticari kullanıma izin veriyor; 21 Kasım'da model kartlarından kontrol edildi)
# ad: (depo, dosya, varsayılan ağırlık, tetik kelimesi, lisans)
STYLE_LORAS = {
    # 21 Kasım karşılaştırması: çizgi filmde karakter sayfası sorununu çözdü, tek temiz figür
    "cartoon": ("issaccyj/lora-sdxl-cartoonillustration", "pytorch_lora_weights.safetensors", 0.8, "in szn style", "openrail++"),
    # gerçek chibi oranı (büyük kafa); model kartı 0.75-0.9 öneriyor
    "chibi": ("strkyyy/anime-chibi", "anime-chibi.safetensors", 0.75, "ch1b1n1me", "openrail++"),
    # atmosfer güzel ama 0.8'de arka planı koyu/dokulu yapıyor → sitede henüz kapalı, sadece API'de (daha düşük ağırlık)
    "dark": ("Geroloq/darkfantasy_style_LoRA", "pytorch_lora_weights.safetensors", 0.5, "in DARK FANTASY style", "openrail++"),
}
# Denenip elenenler (21 Kasım): ntc-ai/SDXL-LoRA-slider.cartoon (mit; karakter sayfası sorunu sürdü),
# ntc-ai/SDXL-LoRA-slider.extremely-detailed (mit; HD'de fark yok denecek kadar az)
IPA_REPO = "h94/IP-Adapter"
IPA_FILE = "ip-adapter_sdxl_vit-h.safetensors"

# DERSLER — üretimlerde tekrar eden hatalardan çıkarılan kurallar (bkz. DERSLER.md).
# Tarifte anahtar kelime geçerse: negatife eklenir; iki_asama=True ise pixel stilinde önce detaylı bir taslak
# çizilir, sonra o taslak referans (IP-Adapter 0.4) verilerek pixel'e çevrilir (nesneler bozulmasın diye).
# "kontrol": (iyi, kötü) → taslak adayları CLIP ile puanlanır, nesnesi gerçekten çizilmiş olan seçilir.
# Dikkat (22 Kasım): negatifi fazla sert yazma — "staff, branch, spear" yasaklanınca kaval tamamen kayboldu.
# Yeni bir hata tekrar ederse buraya bir satır ekle + DERSLER.md'ye yaz.
DERSLER = [
    {"ad": "kaval", "anahtar": ["flute", "fife", "recorder", "piper", "pied piper", "kaval", "pan pipe"],
     "negatif": "violin, fiddle, walking stick, cane, second flute", "iki_asama": True,
     "kontrol": ("a person playing a wooden flute held at the lips", "a person with empty hands")},
    {"ad": "keman", "anahtar": ["violin", "fiddle", "violinist", "keman"],
     "negatif": "walking stick, cane, pole, briefcase, guitar", "iki_asama": True,
     "kontrol": ("a person holding a violin", "a person holding a stick")},
    {"ad": "kitap", "anahtar": ["book", "spellbook", "tome", "grimoire", "kitap"],
     "negatif": "briefcase, suitcase", "iki_asama": True,
     "kontrol": ("a person holding a book", "a person holding a bag")},
    {"ad": "silah", "anahtar": ["sword", "axe", "bow", "rifle", "gun", "dagger", "kılıç"],
     "negatif": "second sword, floating weapon", "iki_asama": True},
    {"ad": "insan kulağı", "anahtar": ["human", "man", "woman", "boy", "girl", "piper", "scholar", "knight", "wizard", "farmer", "soldier", "king", "queen"],
     "haric": ["elf", "elven", "goblin", "orc", "fairy", "pointed ears", "demon", "devil", "vampire", "gnome"],
     "negatif": "elf ears, pointed ears"},
]


def dersleri_uygula(prompt, negative):
    """Tarife uyan dersleri bulur → (yeni negatif, uygulanan ders adları, iki aşama gerekli mi)."""
    import re

    p = prompt.lower()
    has = lambda w: re.search(r"(?<![a-zçğıöşü])" + re.escape(w) + r"(?![a-zçğıöşü])", p) is not None
    adlar, ekler, iki = [], [], False
    dersleri_uygula.kontrol = []
    for d in DERSLER:
        if any(has(w) for w in d["anahtar"]) and not any(has(w) for w in d.get("haric", [])):
            adlar.append(d["ad"])
            if d.get("kontrol"):
                dersleri_uygula.kontrol.append(d["kontrol"])
            ekler += [x.strip() for x in d["negatif"].split(",") if x.strip() and x.strip() not in negative]
            iki = iki or d.get("iki_asama", False)
    ekler = list(dict.fromkeys(ekler))
    # Ders (22 Kasım gece): "battle axe" istenen aslan adama model fazladan bir kılıç ekledi (bacağın içinden geçen).
    # Yasaklamak yerine (yasaklanan şeyin yerine başka bir şey çıkıyor) elin ne yapacağını tarife yaz + taslakları
    # CLIP ile "tek silah" / "fazladan silah" diye puanlayıp temiz olanı seç.
    dersleri_uygula.ek = ""
    silahlar = [en for w, en in SILAHLAR if has(w)]
    silahlar = list(dict.fromkeys(silahlar))
    silahlar = [x for x in silahlar if not any(x != y and x in y for y in silahlar)]  # "axe" ⊂ "battle axe"
    karakter = any(has(w) for w in KARAKTER_KELIME) and not any(has(w) for w in ("game item", "game icon", "icon", "item"))
    cift = any(has(w) for w in ("dual", "two", "both", "pair", "weapons", "arsenal", "twin", "and a sword", "and sword"))
    if len(silahlar) == 1 and karakter and not cift:
        w = silahlar[0]
        if has("shield"):
            dersleri_uygula.ek = f", holding a single {w} in one hand and the shield in the other hand"
        elif w in IKI_EL:
            dersleri_uygula.ek = f", wielding a single {w} with both hands"
        else:
            dersleri_uygula.ek = f", holding a single {w}, the other hand empty"
        # CLIP tüm resme bakınca silah sayamıyor (22 Kasım silah_dene: kılıçlı/kılıçsız farkı yok) → özel kontrol:
        # CLIPSeg "weapon" bölgelerini say (kılıçlı aslanlarda 3 parça, sadece baltalıda 1)
        dersleri_uygula.kontrol.append(("__tek_silah__", w))
        adlar.append("tek silah")
    return (negative + (", " + ", ".join(ekler) if ekler else ""))[:900], adlar, iki


# tarif kelimesi → İngilizce silah adı (en uzunlar önce: "battle axe" "axe"den önce)
SILAHLAR = [("battle axe", "battle axe"), ("war hammer", "war hammer"), ("warhammer", "war hammer"), ("axe", "axe"),
            ("sword", "sword"), ("katana", "katana"), ("hammer", "hammer"), ("spear", "spear"), ("mace", "mace"),
            ("halberd", "halberd"), ("bow", "bow"), ("crossbow", "crossbow"), ("dagger", "dagger"), ("rifle", "rifle"),
            ("shotgun", "shotgun"), ("pistol", "pistol"), ("gun", "gun"), ("club", "club"), ("scythe", "scythe"),
            ("kılıç", "sword"), ("balta", "axe"), ("mızrak", "spear"), ("hançer", "dagger"), ("tüfek", "rifle")]
IKI_EL = {"battle axe", "war hammer", "axe", "sword", "katana", "hammer", "spear", "mace", "halberd", "rifle", "shotgun", "club", "scythe"}
KARAKTER_KELIME = ["character", "enemy", "warrior", "knight", "hero", "soldier", "man", "woman", "boy", "girl", "creature",
                   "monster", "orc", "goblin", "zombie", "skeleton", "barbarian", "hunter", "holding", "wielding", "player"]


def download_models():
    from huggingface_hub import snapshot_download, hf_hub_download

    snapshot_download(
        BASE,
        allow_patterns=["*.json", "*.txt", "unet/*.fp16.safetensors", "text_encoder*/*.fp16.safetensors",
                        "tokenizer*/*", "scheduler/*", "model_index.json"],
    )
    snapshot_download(VAE, allow_patterns=["*.json", "*.safetensors"])
    hf_hub_download(PIXEL_LORA, PIXEL_LORA_FILE)
    for ad, (repo, dosya, *_r) in STYLE_LORAS.items():
        try:
            hf_hub_download(repo, dosya)
        except Exception as e:  # noqa — bir LoRA inmezse motor yine kurulsun
            print(f"[lora] {ad} indirilemedi: {e}", flush=True)
    # IP-Adapter (referans görselle tutarlı karakter) + görüntü kodlayıcı


SEG_MODEL = "CIDAS/clipseg-rd64-refined"
CLIP_MODEL = "openai/clip-vit-large-patch14"


def download_check():
    """Parça bulucu (CLIPSeg) + benzerlik ölçer (CLIP): otomatik parça kontrolü/düzeltmesi için."""
    from huggingface_hub import snapshot_download

    snapshot_download(SEG_MODEL, allow_patterns=["*.json", "*.txt", "*.safetensors", "*.bin"])
    snapshot_download(CLIP_MODEL, allow_patterns=["*.json", "*.txt", "*.safetensors"])


# Yapay zekâ animasyonu (madde 2): poz ControlNet'i. xinsir (Apache-2.0, ticari serbest). thibaud/controlnet-openpose-sdxl
# "other" lisanslı (OpenPose'un ticari olmayan lisansına bağlı) → kullanılmadı (23 Kasım, model kartı kontrolü).
CN_POSE = "xinsir/controlnet-openpose-sdxl-1.0"


def download_cn():
    from huggingface_hub import snapshot_download

    snapshot_download(CN_POSE, allow_patterns=["config.json", "diffusion_pytorch_model.safetensors"])


def download_ipa():
    from huggingface_hub import hf_hub_download, snapshot_download

    hf_hub_download(IPA_REPO, IPA_FILE, subfolder="sdxl_models")
    snapshot_download(IPA_REPO, allow_patterns=["models/image_encoder/*"])


# Arka plan silme modeli. 22 Kasım: isnet-general-use gri baltayı ve onu tutan eli sildi (beyaz gömlek sorunuyla aynı
# aile: figürün parçasını arka plan sanıyor). BiRefNet (MIT lisans) aynı görselde balta + eli eksiksiz ayırdı.
# "lite" sürüm CPU'da ~2 kat hızlı, sonuç aynı. Eskiye dönüş: REMBG_MODEL = "isnet-general-use"
REMBG_MODEL = "birefnet-general-lite"


def download_rembg():
    from rembg import new_session

    new_session("isnet-general-use")
    try:
        new_session(REMBG_MODEL)
    except Exception as e:  # noqa — inmezse isnet ile devam
        print(f"[rembg] {REMBG_MODEL} indirilemedi: {e}", flush=True)


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
    İçeride kalan şeffaf boşluk arka plan rengine benzemiyorsa geri doldurulur.
    22 Kasım: arka plan düz değil de ortası açık (vinyet) olunca kol-gövde arasındaki gerçek boşluklar gri yama olarak
    geri geliyordu → tek renk yerine YEREL arka plan tahmini (figür dışındaki piksellerin geniş bulanıklığı) ile kıyasla."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage

    a = np.array(cut.convert("RGBA"))
    opaque = a[..., 3] >= 110
    holes = ndimage.binary_fill_holes(opaque) & ~opaque
    if not holes.any():
        return cut
    rgbf = orig_rgb.astype(np.float32)
    dis = (~ndimage.binary_fill_holes(opaque)).astype(np.float32)  # figürün dışı = kesin arka plan
    sig = max(orig_rgb.shape[:2]) / 12
    agirlik = ndimage.gaussian_filter(dis, sig)
    yerel = np.stack([ndimage.gaussian_filter(rgbf[..., c] * dis, sig) for c in range(3)], -1) / np.maximum(agirlik, 1e-3)[..., None]
    yerel = np.where((agirlik > 0.02)[..., None], yerel, np.asarray(bg, np.float32))
    d = np.minimum(np.sqrt(((rgbf - yerel) ** 2).sum(-1)), np.sqrt(((rgbf - np.asarray(bg)) ** 2).sum(-1)))
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
    .run_function(download_check)
    .run_function(download_cn)
    .add_local_file(Path(__file__).parent / "pozlar.py", "/root/pozlar.py")
)

app = modal.App(APP_NAME, image=image)


@app.cls(
    gpu="T4",
    cpu=4.0,  # arka plan silme (BiRefNet) CPU'da çalışır; 4 çekirdekle ~5-10 sn
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
            pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="dpmsolver++", solver_type="midpoint",
            final_sigmas_type="zero", timestep_spacing="leading", steps_offset=1  # DreamShaper DEIS ayarıyla gelir
        )
        pipe.load_lora_weights(PIXEL_LORA, weight_name=PIXEL_LORA_FILE, adapter_name="pixel")
        self.loras = {}
        for ad, (repo, dosya, w, tetik, _lis) in STYLE_LORAS.items():
            try:
                pipe.load_lora_weights(repo, weight_name=dosya, adapter_name=ad)
                self.loras[ad] = (w, tetik)
            except Exception as e:  # noqa
                print(f"[lora] {ad} yüklenemedi: {e}", flush=True)
        print(f"[lora] yüklü stil LoRA'ları: {list(self.loras)}", flush=True)
        self._lora = (None, None)
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
        from transformers import CLIPModel, CLIPProcessor, CLIPSegForImageSegmentation, CLIPSegProcessor

        self.seg_proc = CLIPSegProcessor.from_pretrained(SEG_MODEL)
        self.seg = CLIPSegForImageSegmentation.from_pretrained(SEG_MODEL).to("cuda").eval()
        self.clip_proc = CLIPProcessor.from_pretrained(CLIP_MODEL)
        self.clip = CLIPModel.from_pretrained(CLIP_MODEL, torch_dtype=torch.float16, use_safetensors=True).to("cuda").eval()
        from rembg import new_session

        self.rb = new_session("isnet-general-use")
        try:
            self.rb = new_session(REMBG_MODEL)
        except Exception as e:  # noqa
            print(f"[rembg] {REMBG_MODEL} açılamadı, isnet kullanılıyor: {e}", flush=True)

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
            # sahne/desenli arka plan: yine de ana figürü çıkarmayı dene; tek ve makul boyutlu bir figür çıkarsa onu ver
            try:
                from scipy import ndimage

                cut = drop_debris(remove(im.convert("RGB"), session=self.rb, post_process_mask=True))
                al = np.array(cut)[..., 3] > 0
                frac = float(al.mean())
                lab, n = ndimage.label(al, structure=np.ones((3, 3)))
                if n and 0.04 < frac < 0.85:
                    big = np.bincount(lab.ravel())[1:].max() / max(1, al.sum())
                    if big > 0.7:
                        self.last_plain = True  # figür başarıyla ayrıldı
                        return cut
            except Exception as e:  # noqa
                print("sahne kesimi olmadı:", e)
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

    def _lora_prompt(self, prompt):
        """Stil LoRA'sı seçiliyse tetik kelimesini tarife ekler."""
        ad, _w = getattr(self, "_lora", (None, None))
        if ad in getattr(self, "loras", {}):
            tetik = self.loras[ad][1]
            if tetik.lower() not in prompt.lower():
                return f"{prompt}, {tetik}"
        return prompt

    def _lora_sec(self, body):
        """İstekten stil LoRA'sı: {"lora": "cartoon"|"chibi"|"dark", "lora_weight": 0-2}"""
        ad = body.get("lora")
        if not ad or ad not in getattr(self, "loras", {}):
            return (None, None)
        w = body.get("lora_weight")
        return (ad, None if w is None else max(0.0, min(2.0, float(w))))

    def _common(self, style, ref_img, ref_scale):
        ad, w = getattr(self, "_lora", (None, None))
        adlar, agirlik = ["pixel"], [1.0 if style == "pixel" else 0.0]
        if ad in getattr(self, "loras", {}):  # seçilen stil LoRA'sı açılır, diğerleri kapalı kalır
            adlar.append(ad)
            agirlik.append(float(w) if w is not None else self.loras[ad][0])
        self.pipe.set_adapters(adlar, adapter_weights=agirlik)
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
        prompt = self._lora_prompt(prompt)
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

    def _part_mask(self, im, name):
        """CLIPSeg ile resimdeki parçanın (ör. 'head') maskesi → (PIL L maskesi, alan oranı, kutu)."""
        import numpy as np
        import torch
        from PIL import Image, ImageFilter

        with torch.no_grad():
            inp = self.seg_proc(text=[name], images=[im], return_tensors="pt").to("cuda")
            try:  # CLIPSeg 352px girişle eğitildi; yeni transformers boyut kontrolü için konum kodlaması uyarlanır
                logits = self.seg(**inp, interpolate_pos_encoding=True).logits
            except TypeError:
                inp = self.seg_proc(text=[name], images=[im.resize((224, 224))], return_tensors="pt",
                                    size={"height": 224, "width": 224}).to("cuda")
                logits = self.seg(**inp).logits
        prob = torch.sigmoid(logits).squeeze().float().cpu().numpy()
        m = Image.fromarray((prob * 255).astype(np.uint8)).resize(im.size, Image.BILINEAR)
        a = np.array(m) > 100
        if a.mean() < 0.004:
            return None, 0.0, None
        ys, xs = np.nonzero(a)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        grow = max(8, int(0.03 * max(im.size)))
        mask = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(grow // 2 * 2 + 1))
        mask = mask.filter(ImageFilter.GaussianBlur(grow / 2))  # yumuşak kenar: yeni çizim çevreye kademeli karışır
        return mask, float(a.mean()), box

    def _clip_pref(self, crop, good, bad):
        """Kırpılan bölge 'good' tarifine mi 'bad' tarifine mi benziyor → good olasılığı (0-1)."""
        import torch

        with torch.no_grad():
            inp = self.clip_proc(text=[good, bad], images=crop, return_tensors="pt", padding=True).to("cuda")
            inp["pixel_values"] = inp["pixel_values"].half()
            p = self.clip(**inp).logits_per_image.float().softmax(-1)[0, 0].item()
        return p

    def _score(self, im, parts, absent, base, detay=False):
        """Görsel tarife ne kadar uyuyor. Gövde yapısı (olmaması gereken parçalar yok mu) öncelikli,
        çünkü sonradan silmek iz bırakır; istenen parçalar (ör. kafa) sonradan temizce düzeltilebilir."""
        im = im.convert("RGB")
        parca_puan, yok_puan = [], []
        for part in (parts or [])[:3]:
            name, want = str(part.get("name", "")), str(part.get("want", ""))
            if not name or not want:
                continue
            mask, oran, box = self._part_mask(im, name)
            if mask is None:
                parca_puan.append(0.0)
                continue
            pad = int(0.1 * max(box[2] - box[0], box[3] - box[1]))
            crop = im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))
            parca_puan.append(self._clip_pref(crop, want, f"{base} {name}" if base else f"ordinary {name}"))
        for name in (absent or [])[:3]:
            mask, oran, _ = self._part_mask(im, str(name))
            yok_puan.append(1.0 - min(1.0, oran * 25))  # parça alanı %4 ve üstü → tam ceza
        yapi = min(yok_puan) if yok_puan else 1.0
        parca = sum(parca_puan) / len(parca_puan) if parca_puan else 1.0
        toplam = 0.7 * yapi + 0.3 * parca
        if detay:
            return toplam, yapi, parca_puan
        return toplam

    def _sec(self, prompt, negative, width, height, seed, ipa, parts, absent, base, aday=4):
        """Baştan doğru çizim: hızlı taslaklar üret, tarife en uygun olanın seed'ini seç."""
        import torch

        sonuc = []
        for i in range(0, aday, 2):
            seeds = [seed + 1000 * j for j in range(i, min(aday, i + 2))]
            ims = self.pipe(prompt=prompt, negative_prompt=negative, num_inference_steps=12, guidance_scale=6.0,
                            width=width, height=height, num_images_per_prompt=len(seeds),
                            generator=[torch.Generator("cuda").manual_seed(x) for x in seeds],
                            ip_adapter_image=ipa).images
            for x, im in zip(seeds, ims):
                sonuc.append((self._score(im, parts, absent, base), x))
        sonuc.sort(reverse=True)
        return sonuc[0][1], sonuc[0][0], [round(p, 2) for p, _ in sonuc]

    def _sec_kontrol(self, prompt, negative, width, height, seed, ipa, kontrol, aday=4):
        """Hızlı taslaklar → ders kontrol çiftleriyle (iyi, kötü) CLIP puanı → en iyi seed."""
        import torch

        sonuc = []
        for i in range(0, aday, 2):
            seeds = [seed + 1000 * j for j in range(i, min(aday, i + 2))]
            ims = self.pipe(prompt=prompt, negative_prompt=negative, num_inference_steps=12, guidance_scale=6.0,
                            width=width, height=height, num_images_per_prompt=len(seeds),
                            generator=[torch.Generator("cuda").manual_seed(x) for x in seeds],
                            ip_adapter_image=ipa).images
            for x, im in zip(seeds, ims):
                sonuc.append((self._kontrol_puan(im, kontrol), x))
        sonuc.sort(reverse=True)
        return sonuc[0][1], sonuc[0][0], [round(p, 2) for p, _ in sonuc]

    def _puan(self, im, prompt, kontrol=None):
        """Görselin tarife uyumu 0-1: CLIP metin-görsel benzerliği (+ varsa ders kontrolü). Adayları sıralamak için."""
        import torch

        with torch.no_grad():
            inp = self.clip_proc(text=[prompt], images=im.convert("RGB"), return_tensors="pt", padding=True,
                                 truncation=True, max_length=77).to("cuda")
            inp["pixel_values"] = inp["pixel_values"].half()
            cos = self.clip(**inp).logits_per_image.float()[0, 0].item() / 100.0
        uyum = max(0.0, min(1.0, (cos - 0.15) / 0.2))
        if kontrol:
            return 0.5 * uyum + 0.5 * self._kontrol_puan(im, kontrol)
        return uyum

    def _silah_sayisi(self, im, esik=0.3, min_alan=0.008):
        """CLIPSeg 'weapon' olasılık haritasında ayrı büyük bölge sayısı (fazladan silah algılama)."""
        import numpy as np
        import torch
        from PIL import Image
        from scipy import ndimage

        im = im.convert("RGB")
        with torch.no_grad():
            inp = self.seg_proc(text=["weapon"], images=[im], return_tensors="pt").to("cuda")
            try:
                lg = self.seg(**inp, interpolate_pos_encoding=True).logits
            except TypeError:
                inp = self.seg_proc(text=["weapon"], images=[im.resize((224, 224))], return_tensors="pt",
                                    size={"height": 224, "width": 224}).to("cuda")
                lg = self.seg(**inp).logits
        pr = torch.sigmoid(lg).squeeze().float().cpu().numpy()
        a = np.array(Image.fromarray((pr * 255).astype(np.uint8)).resize(im.size, Image.BILINEAR)) > esik * 255
        lab, n = ndimage.label(a)
        if not n:
            return 0
        return int((np.bincount(lab.ravel())[1:] > min_alan * a.size).sum())

    def _kontrol_puan(self, im, kontrol):
        """Ders kontrol çiftleri: (iyi, kötü) → CLIP tercihi; ("__tek_silah__", ad) → silah bölgesi sayısı (1 → 1.0)."""
        puan = []
        for iyi, kotu in kontrol:
            if iyi == "__tek_silah__":
                k = self._silah_sayisi(im)
                puan.append(1.0 if k <= 1 else 0.5 if k == 2 else 0.0)
            else:
                puan.append(self._clip_pref(im, iyi, kotu))
        return sum(puan) / max(1, len(puan))

    def _fix_parts(self, im, parts, base, style_text, negative, seed, ipa, absent=None, full_prompt=""):
        """Tarifteki parçalar resimde tutmamışsa o bölgeyi bulup yeniden çizer; olmaması gereken parçaları siler. Kayıt döner."""
        import numpy as np
        import torch
        from PIL import Image

        log = []
        im = im.convert("RGB")
        degisti = False
        # 1) olmaması gereken parçalar (ör. yılanda bacak): bulunursa o bölgeyi gövdenin devamı olarak yeniden çiz
        for j, name in enumerate((absent or [])[:3]):
            name = str(name).strip()[:30]
            if not name:
                continue
            mask, oran, box = self._part_mask(im, name)
            if mask is None or oran < 0.01:
                log.append({"parca": name, "durum": "yok ✓"})
                continue
            g = torch.Generator("cuda").manual_seed(seed + 211 + j)
            govde = f"{base} body" if base else "body"
            im = self.inp(prompt=f"smooth continuous {govde}, seamless, {style_text}",
                          negative_prompt=f"{name}, limbs, {negative}", image=im, mask_image=mask,
                          width=im.width, height=im.height, strength=0.95, num_inference_steps=28,
                          guidance_scale=7.0, generator=g, ip_adapter_image=ipa).images[0]
            degisti = True
            m2, oran2, _ = self._part_mask(im, name)
            log.append({"parca": name, "durum": "silindi" if (m2 is None or oran2 < oran * 0.5) else "silinemedi"})
        for i, part in enumerate(parts[:3]):
            name = str(part.get("name", "")).strip()[:40]
            want = str(part.get("want", "")).strip()[:200]
            if not name or not want:
                continue
            for deneme in range(2):
                mask, oran, box = self._part_mask(im, name)
                if mask is None:
                    log.append({"parca": name, "durum": "bulunamadı"})
                    break
                pad = int(0.1 * max(box[2] - box[0], box[3] - box[1]))
                crop = im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))
                bad = f"{base} {name}" if base else f"ordinary {name}"
                p = self._clip_pref(crop, want, bad)
                if p >= 0.55:
                    log.append({"parca": name, "durum": "tuttu" if deneme == 0 else "düzeltildi", "skor": round(p, 2)})
                    break
                if deneme == 1:
                    log.append({"parca": name, "durum": "zayıf kaldı", "skor": round(p, 2)})
                    break
                g = torch.Generator("cuda").manual_seed(seed + 101 + i)
                degisti = True
                im = self.inp(prompt=f"{want}, {style_text}", negative_prompt=negative, image=im, mask_image=mask,
                              width=im.width, height=im.height, strength=0.92, num_inference_steps=28,
                              guidance_scale=7.0, generator=g, ip_adapter_image=ipa).images[0]
        # son kat cila: yamaların dokusunu/ışığını bütünle eşitle (hafif img2img)
        if degisti and full_prompt:
            g = torch.Generator("cuda").manual_seed(seed + 977)
            im = self.i2i(prompt=full_prompt, negative_prompt=negative, image=im, strength=0.3,
                          num_inference_steps=30, guidance_scale=6.0, generator=g, ip_adapter_image=ipa).images[0]
            log.append({"parca": "bütün", "durum": "cilalandı"})
        return im, log

    def _hires(self, out, prompt, negative, seed, ipa, oran=1.5, strength=0.35, uzun=1536, alan=1.65e6):
        """İki aşamalı üretim (hi-res fix): görseli büyütüp hafif img2img ile ince detayları yeniden çizer.
        Uzun kenar en fazla 1536 (T4 belleği); sadece pixel olmayan stillerde (pixel ızgarası bulanıklaşır)."""
        import torch
        from PIL import Image

        yeni = []
        self.pipe.enable_vae_tiling()  # 1536'da VAE çözme belleği taşmasın
        try:
            for k, im in enumerate(out):
                # 23 Kasım: kare 1024 görsel 1536x1536'ya çıkınca T4'te üretim 500 hatası verdi → toplam piksel de sınırlı
                # (832x1216 → 1088x1536 ≈ 1.65 MP sorunsuz çalışıyordu)
                s = min(oran, uzun / max(im.size), (alan / (im.width * im.height)) ** 0.5)
                if s <= 1.05:
                    yeni.append(im); continue
                W, H = max(64, round(im.width * s / 64) * 64), max(64, round(im.height * s / 64) * 64)
                big = im.convert("RGB").resize((W, H), Image.LANCZOS)
                g = torch.Generator("cuda").manual_seed(seed + 500 + k)
                torch.cuda.empty_cache()
                try:
                    yeni.append(self.i2i(prompt=prompt, negative_prompt=negative, image=big, strength=strength,
                                         num_inference_steps=30, guidance_scale=6.0, generator=g,
                                         ip_adapter_image=ipa).images[0])
                except torch.cuda.OutOfMemoryError:  # bellek yetmezse görsel ilk haliyle kalsın, istek düşmesin
                    print("[hires] bellek yetmedi, ilk hali veriliyor", flush=True)
                    torch.cuda.empty_cache()
                    yeni.append(im)
                torch.cuda.empty_cache()
        finally:
            self.pipe.disable_vae_tiling()
        return yeni

    def _yuz_kutu(self, im):
        """CLIPSeg 'face' haritasında en güçlü tek bölge → (kutu, yumuşak maske PIL L) ya da (None, None).
        Birden çok bölge çıkarsa (yüz + el gibi) olasılık toplamı en büyük olan alınır."""
        import numpy as np
        import torch
        from PIL import Image, ImageFilter
        from scipy import ndimage

        with torch.no_grad():
            inp = self.seg_proc(text=["face"], images=[im], return_tensors="pt").to("cuda")
            try:
                lg = self.seg(**inp, interpolate_pos_encoding=True).logits
            except TypeError:
                inp = self.seg_proc(text=["face"], images=[im.resize((224, 224))], return_tensors="pt",
                                    size={"height": 224, "width": 224}).to("cuda")
                lg = self.seg(**inp).logits
        pr = torch.sigmoid(lg).squeeze().float().cpu().numpy()
        pr = np.array(Image.fromarray((pr * 255).astype(np.uint8)).resize(im.size, Image.BILINEAR)).astype(np.float32) / 255
        a = pr > 0.35
        lab, n = ndimage.label(a)
        if not n:
            return None, None
        guc = ndimage.sum(pr, lab, index=np.arange(1, n + 1))
        k = int(np.argmax(guc)) + 1
        if guc[k - 1] < 30:  # çok küçük/zayıf: yüz yok sayılır
            return None, None
        ys, xs = np.nonzero(lab == k)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        m = Image.fromarray(((lab == k) * 255).astype(np.uint8))
        buy = max(5, int(0.25 * max(box[2] - box[0], box[3] - box[1])))
        m = m.filter(ImageFilter.MaxFilter(buy // 2 * 2 + 1)).filter(ImageFilter.GaussianBlur(buy / 2))
        return box, m

    def _yuz_duzelt(self, im, prompt, negative, seed, ipa, strength=0.4, hedef=1024):
        """0d Yüz düzeltme: yüzü bul, çevresini kırp, hedef çözünürlüğe büyütüp hafif img2img ile yeniden çiz,
        küçültüp yumuşak maskeyle geri yapıştır (küçük yüzler tam boy görselde silik/bozuk çıkıyor)."""
        import re

        import numpy as np
        import torch
        from PIL import Image

        im = im.convert("RGB")
        box, m = self._yuz_kutu(im)
        if box is None:
            return im, {"durum": "yüz bulunamadı"}
        fw, fh = box[2] - box[0], box[3] - box[1]
        fs = max(fw, fh)
        if fs < 14:
            return im, {"durum": "yüz çok küçük", "boyut": fs}
        side = int(min(min(im.size), max(96, fs * 2.2)))
        if side >= 0.8 * hedef:
            return im, {"durum": "yüz zaten büyük", "boyut": fs}
        cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
        x0 = max(0, min(im.width - side, cx - side // 2))
        y0 = max(0, min(im.height - side, cy - side // 2))
        cb = (x0, y0, x0 + side, y0 + side)
        crop = im.crop(cb).resize((hedef, hedef), Image.LANCZOS)
        # tarifteki "tam boy / ayaklar" gibi kompozisyon sözleri yüz kırpıntısını şaşırtır → çıkar, yüz vurgusu ekle
        p = re.sub(r"(?i)\b(full body|whole body visible|full figure|standing|feet|boots|shoes)\b,?", "", prompt)
        p = re.sub(r"\s*,(\s*,)+", ",", p).strip(" ,")
        p = f"detailed face, clear expressive eyes, well drawn facial features, {p}"[:1500]
        g = torch.Generator("cuda").manual_seed(seed + 733)
        yeni = self.i2i(prompt=p, negative_prompt=negative + ", deformed face, blurry face, extra eyes, asymmetric eyes",
                        image=crop, strength=strength, num_inference_steps=30, guidance_scale=6.0, generator=g,
                        ip_adapter_image=ipa).images[0].resize((side, side), Image.LANCZOS)
        # maske: yüz bölgesi (yumuşak) × kırpıntı kenarına doğru sönen pencere (dikiş olmasın)
        mk = np.array(m.crop(cb)).astype(np.float32) / 255
        r = np.minimum(np.arange(side), np.arange(side)[::-1]).astype(np.float32) / max(1, side * 0.12)
        pencere = np.clip(np.minimum.outer(r, r), 0, 1)
        mk = Image.fromarray((np.clip(mk * pencere, 0, 1) * 255).astype(np.uint8))
        im.paste(yeni, cb[:2], mk)
        return im, {"durum": "düzeltildi", "boyut": fs, "kirpinti": side}

    def _run(self, prompt, negative, seed, n, width, height, style, transparent=False, auto=False, native=False,
             ref_img=None, ref_scale=0.6, tileable=False, parts=None, base="", style_text="", absent=None, hires=False,
             kontrol=None, yuz=False):
        import base64
        import io
        import re
        import time

        import torch

        t0 = time.time()
        ipa = self._common(style, ref_img, ref_scale)
        prompt = self._lora_prompt(prompt)
        secimler = []
        if (parts or absent) and not tileable:
            # her istenen görsel için 4 taslak tara, en doğru kompozisyonun seed'ini kullan
            seeds = []
            for k in range(n):
                sd, puan, hepsi = self._sec(prompt, negative, width, height, seed + k, ipa, parts, absent, base)
                seeds.append(sd)
                secimler.append({"parca": "taslak", "durum": f"4 taslaktan en iyisi seçildi", "skor": round(puan, 2), "adaylar": hepsi})
            gens = [torch.Generator("cuda").manual_seed(x) for x in seeds]
        elif kontrol and not tileable:
            # ders kontrolü (ör. tek silah): 4 hızlı taslak, CLIP ile "iyi" tarife en yakın olanın seed'i
            seeds = []
            for k in range(n):
                sd, puan, hepsi = self._sec_kontrol(prompt, negative, width, height, seed + k, ipa, kontrol)
                seeds.append(sd)
                secimler.append({"parca": "taslak", "durum": "4 taslaktan en iyisi seçildi", "skor": round(puan, 2), "adaylar": hepsi})
            gens = [torch.Generator("cuda").manual_seed(x) for x in seeds]
        else:
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
        fixes = []
        if (parts or absent) and not tileable:
            yeni = []
            for k, im in enumerate(out):
                log = [secimler[k]] if k < len(secimler) else []
                try:
                    son, yapi, pp = self._score(im, parts, absent, base, detay=True)
                    if yapi >= 0.9 and all(x >= 0.55 for x in pp):
                        log.append({"parca": "sonuç", "durum": "tarife uygun", "skor": round(son, 2)})
                    else:  # nadir: seçilen taslak bile tam tutmadıysa parçayı düzelt (yedek yol)
                        im, l2 = self._fix_parts(im, parts or [], base, style_text, negative, seed + k, ipa, absent, prompt)
                        log += l2
                except Exception as e:  # noqa
                    log.append({"hata": str(e)[:200]})
                yeni.append(im); fixes.append(log)
            out = yeni
        elif secimler:
            fixes = [[x] for x in secimler]
        # En iyisini seç (0e): her adayı tarife uyum (CLIP) + ders kontrolüyle puanla, en iyisini başa al
        puanlar = []
        if not tileable:
            try:
                puanlar = [self._puan(im, prompt, kontrol) for im in out]
                if len(out) > 1:
                    sira = sorted(range(len(out)), key=lambda k: -puanlar[k])
                    out = [out[k] for k in sira]
                    puanlar = [puanlar[k] for k in sira]
                    if fixes:
                        fixes = [fixes[k] for k in sira]
            except Exception as e:  # noqa
                print("puanlama olmadı:", e, flush=True)
        hires = bool(hires) and style != "pixel" and not tileable
        t1 = time.time()
        if hires:
            out = self._hires(out, prompt, negative, seed, ipa)
        hs = round(time.time() - t1, 2)
        # 0d Yüz düzeltme: karakterlerde küçük yüzü yüksek çözünürlükte yeniden çiz (pixel/doku/arkadan görünüşte kapalı)
        yuz = bool(yuz) and style != "pixel" and not tileable and not re.search(r"(?i)\b(back view|from behind|facing away)\b", prompt)
        yuz_log, ys = [], 0.0
        if yuz:
            t2 = time.time()
            yeni = []
            for k, im in enumerate(out):
                try:
                    im, lg = self._yuz_duzelt(im, prompt, negative, seed + k, ipa)
                except Exception as e:  # noqa — yüz düzeltme olmazsa görsel olduğu gibi kalsın
                    lg = {"durum": "hata", "hata": str(e)[:200]}
                yeni.append(im); yuz_log.append(lg)
            out = yeni
            ys = round(time.time() - t2, 2)
        imgs, grids, plains = self._post(out, transparent, auto, style, native)
        r = {"images": imgs, "grid": grids, "plain": plains, "fixes": fixes, "puan": [round(x, 3) for x in puanlar],
             "seconds": round(time.time() - t0, 2)}
        if hires:
            r["hires"] = True
            r["hires_seconds"] = hs  # sadece büyütme + yeniden çizim süresi
        if yuz:
            r["yuz"] = yuz_log
            r["yuz_seconds"] = ys
        return r

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
            return {"ok": True, "motor": "sdxl+pixel-art-xl+ip-adapter", "model": BASE, "gpu": "T4",
                    "loralar": list(getattr(self, "loras", {})),
                    "ozellikler": ["generate", "reference", "tileable", "edit", "inpaint", "rembg", "hires", "yuz"]}

        # 23 Kasım: Modal web uç noktası 150 sn'yi aşan isteklere 303 yönlendirme döner (CORS başlıksız) →
        # tarayıcıda "Failed to fetch". Ekstra kalite + yüz düzeltme + temizlik birlikte ~150-200 sn sürüyor.
        # Çözüm: iş kuyruğu. POST /is/<tür> hemen {"is": id} döner, iş arka planda çalışır, GET /is/<id> ile sorulur.
        # (Tek GPU: kilit; konteyner yoklamalarla açık kalır.) Eski eşzamanlı uç noktalar Actions için duruyor.
        import threading
        import time as _time
        import uuid

        isler = {}
        gpu_kilit = threading.Lock()

        @api.post("/is/{tur}")
        def is_baslat(tur: str, body: dict, x_sprite_key: str = Header(default="")):
            if key and x_sprite_key != key:
                raise HTTPException(status_code=401, detail="Anahtar yanlış")
            fn = {"generate": generate, "edit": edit}.get(tur)
            if fn is None:
                raise HTTPException(status_code=404, detail="bilinmeyen iş türü")
            for k in [k for k, v in isler.items() if _time.time() - v["t0"] > 1800]:
                isler.pop(k, None)  # 30 dk'dan eski, alınmamış sonuçlar
            is_id = uuid.uuid4().hex[:16]
            isler[is_id] = {"durum": "calisiyor", "t0": _time.time()}

            def calis():
                try:
                    isler[is_id].update(durum="bitti", sonuc=fn(body, x_sprite_key))
                except HTTPException as e:
                    isler[is_id].update(durum="hata", kod=e.status_code, detay=str(e.detail)[:1200])
                except Exception as e:  # noqa
                    isler[is_id].update(durum="hata", kod=500, detay=f"{type(e).__name__}: {str(e)[:600]}")

            threading.Thread(target=calis, daemon=True).start()
            return {"is": is_id}

        @api.get("/is/{is_id}")
        def is_durum(is_id: str, x_sprite_key: str = Header(default="")):
            if key and x_sprite_key != key:
                raise HTTPException(status_code=401, detail="Anahtar yanlış")
            d = isler.get(is_id)
            if d is None:
                raise HTTPException(status_code=404, detail="iş bulunamadı (motor yeniden başlamış olabilir)")
            if d["durum"] == "calisiyor":
                return {"durum": "calisiyor", "sure": round(_time.time() - d["t0"])}
            isler.pop(is_id, None)
            return {k: v for k, v in d.items() if k != "t0"}

        @api.post("/generate")
        def generate(body: dict, x_sprite_key: str = Header(default="")):
            if key and x_sprite_key != key:
                raise HTTPException(status_code=401, detail="Anahtar yanlış")
            try:
                with gpu_kilit:
                    return _generate(body)
            except HTTPException:
                raise
            except Exception as e:  # noqa — 23 Kasım: çıplak "500" hata ayıklamayı imkânsız kılıyordu → ayrıntı dön
                import traceback

                iz = traceback.format_exc()
                print(iz, flush=True)
                try:
                    import torch

                    torch.cuda.empty_cache()
                except Exception:  # noqa
                    pass
                raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)[:300]} | {iz[-700:]}")

        def _generate(body):
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
            negative = str(body.get("negative", "text, watermark, blurry, cropped, multiple characters, character sheet, reference sheet, model sheet, multiple poses, inset, close-up panel, multiple views, duplicate, turnaround, ground shadow, cast shadow, drop shadow, shadow under feet, frame, border, card frame, ornamental background, patterned background, wallpaper, scenery, landscape"))[:500]
            transparent = bool(body.get("transparent", False))
            auto = bool(body.get("auto", False))
            native = bool(body.get("native", False))
            ref_img = self._ref(body.get("reference"))
            ref_scale = max(0.0, min(1.0, float(body.get("ref_scale", 0.6))))
            tileable = bool(body.get("tileable", False))
            parts = body.get("parts") if isinstance(body.get("parts"), list) else None
            base = str(body.get("base", ""))[:60]
            style_text = str(body.get("style_text", "high quality 2D game art"))[:200]
            absent = body.get("absent") if isinstance(body.get("absent"), list) else None
            self._lora = self._lora_sec(body)
            dersler, iki = [], False
            if body.get("dersler", True) is not False and not tileable:
                negative, dersler, iki = dersleri_uygula(prompt, negative)
                prompt = (prompt + getattr(dersleri_uygula, "ek", ""))[:1500]
            kontrol_listesi = list(getattr(dersleri_uygula, "kontrol", [])) if dersler else []
            taslak = False
            if iki and style == "pixel" and ref_img is None and body.get("iki_asama", True) is not False:
                # Ders: pixel'de elde tutulan nesneler (kaval, keman, kitap...) bozuluyor → önce detaylı taslak çiz,
                # onu referans verip pixel'e çevir (21-22 Kasım kavalcı denemesi: referanssız kaval sopaya dönüştü, 0.4 referansla düzeldi)
                import re as _re
                tp = _re.sub(r"(?i)\b(pixel art|pixel-art|pixelated|16-bit|8-bit|pixel)\b,?", "", prompt).strip(" ,")
                tp = f"{tp}, detailed 2D game illustration, clean shapes"
                lora_once = self._lora
                self._lora = (None, None)
                kontrol = list(getattr(dersleri_uygula, "kontrol", []))
                try:
                    d0 = self._run(tp, negative, seed, 2 if kontrol else 1, width, height, "other", False, False, False,
                                   None, 0.0, False, None, "", style_text, None)
                    adaylar = [self._ref(x) for x in d0["images"]]
                    puanlar = [self._kontrol_puan(a, kontrol) for a in adaylar] if kontrol else [1.0]
                    eniyi = max(range(len(adaylar)), key=lambda k: puanlar[k])
                    ref_img, ref_scale, taslak = adaylar[eniyi], 0.4, [round(x, 2) for x in puanlar]
                finally:
                    self._lora = lora_once
            r = self._run(prompt, negative, seed, n, width, height, style, transparent, auto, native,
                          ref_img, ref_scale, tileable, parts, base, style_text, absent, bool(body.get("hires", False)),
                          None if taslak else (kontrol_listesi or None), bool(body.get("yuz", False)))
            r["dersler"] = dersler
            r["iki_asama"] = taslak
            return r

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
            with gpu_kilit:
                self._lora = self._lora_sec(body)
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


# ---------------- Yapay zekâ animasyonu (madde 2) ----------------
# Kodla çizilen poz iskeletleri (pozlar.py) + OpenPose ControlNet + IP-Adapter. "Yan yana" yöntem: 2 kat genişlikte
# tuvalin solunda referans karakter (sabit), sağında yeni kare (inpaint) → model aynı resimdeki karakteri kopyalar.
# 23 Kasım denemesi (anim_dene.yml): bağımsız kareler pozu tutturdu ama kıyafet kareden kareye değişti; yan yana
# yöntemde 8 karenin hepsi aynı kıyafet/oran. T4'te bellek yetmedi (SDXL + ControlNet + IP-Adapter ≈ 12,5 GB) → L4.
ANIM_TURLER = {"bekleme": 4, "yuru": 8, "kos": 8, "saldir": 8, "zipla": 6, "hasar": 4}


@app.cls(
    gpu="L4",
    cpu=4.0,
    timeout=900,
    scaledown_window=60,  # 60 sn boşta kalınca kapanır
    max_containers=1,
    secrets=[modal.Secret.from_name("sprite-key")],
)
class Animator:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import (AutoencoderKL, ControlNetModel, DPMSolverMultistepScheduler,
                               StableDiffusionXLControlNetInpaintPipeline, StableDiffusionXLControlNetPipeline)

        vae = AutoencoderKL.from_pretrained(VAE, torch_dtype=torch.float16)
        cn = ControlNetModel.from_pretrained(CN_POSE, torch_dtype=torch.float16)
        pipe = StableDiffusionXLControlNetPipeline.from_pretrained(BASE, vae=vae, controlnet=cn, torch_dtype=torch.float16,
                                                                   variant="fp16", use_safetensors=True)
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="dpmsolver++", solver_type="midpoint",
            final_sigmas_type="zero", timestep_spacing="leading", steps_offset=1)
        pipe.load_lora_weights(PIXEL_LORA, weight_name=PIXEL_LORA_FILE, adapter_name="pixel")
        self.loras = {}
        for ad, (repo, dosya, w, tetik, _l) in STYLE_LORAS.items():
            try:
                pipe.load_lora_weights(repo, weight_name=dosya, adapter_name=ad)
                self.loras[ad] = (w, tetik)
            except Exception as e:  # noqa
                print(f"[lora] {ad} yüklenemedi: {e}", flush=True)
        pipe.load_ip_adapter(IPA_REPO, subfolder="sdxl_models", weight_name=IPA_FILE, image_encoder_folder="models/image_encoder")
        pipe.to("cuda")
        pipe.enable_vae_slicing()
        pipe.enable_vae_tiling()
        self.pipe = pipe
        self.inp = StableDiffusionXLControlNetInpaintPipeline.from_pipe(pipe)
        from rembg import new_session

        try:
            self.rb = new_session(REMBG_MODEL)
        except Exception:  # noqa
            self.rb = new_session("isnet-general-use")
        print("[animator] hazır, GPU bellek", round(torch.cuda.memory_allocated() / 1e9, 1), "GB", flush=True)

    def _stil(self, style, lora, lora_weight=None):
        adlar, ag = ["pixel"], [1.0 if style == "pixel" else 0.0]
        if lora in self.loras:
            adlar.append(lora)
            ag.append(float(lora_weight) if lora_weight is not None else self.loras[lora][0])
        self.pipe.set_adapters(adlar, adapter_weights=ag)

    def _kes(self, im):
        """Arka planı sil + kalıntıları temizle (düz açık gri zemin)."""
        import numpy as np
        from rembg import remove

        rgb = np.array(im.convert("RGB"))
        bg = border_bg(rgb)
        raw = remove(im.convert("RGB"), session=self.rb, post_process_mask=True)
        out = drop_debris(defringe(fill_holes(rgb, raw, bg), bg=bg))
        alan = lambda x: int((np.array(x)[..., 3] > 0).sum())
        return out if alan(out) >= 0.6 * max(1, alan(raw)) else drop_debris(raw)

    def _yan_yana(self, ref, sol_poz, sag_poz, prompt, negative, seed, ip, W, H, steps=22):
        """Solda referans (sabit), sağda pozdaki yeni kare → sağ yarı."""
        import torch
        from PIL import Image

        tuval = Image.new("RGB", (2 * W, H), (200, 200, 200)); tuval.paste(ref, (0, 0))
        kontrol = Image.new("RGB", (2 * W, H)); kontrol.paste(sol_poz, (0, 0)); kontrol.paste(sag_poz, (W, 0))
        maske = Image.new("L", (2 * W, H), 0); maske.paste(255, (W, 0, 2 * W, H))
        self.inp.set_ip_adapter_scale(ip)
        out = self.inp(prompt=prompt, negative_prompt=negative, image=tuval, mask_image=maske, control_image=kontrol,
                       width=2 * W, height=H, strength=1.0, num_inference_steps=steps, guidance_scale=6.0,
                       generator=torch.Generator("cuda").manual_seed(seed), ip_adapter_image=ref,
                       controlnet_conditioning_scale=1.0).images[0]
        return out.crop((W, 0, 2 * W, H))

    def animate(self, body):
        import base64
        import io
        import time

        import numpy as np
        import torch
        from PIL import Image

        import pozlar

        t0 = time.time()
        tur = str(body.get("anim", "yuru"))
        if tur not in ANIM_TURLER:
            raise ValueError(f"animasyon türü: {list(ANIM_TURLER)}")
        n = int(body.get("n") or ANIM_TURLER[tur])
        n = max(2, min(12, n))
        seed = int(body.get("seed", 7)) % (2**31)
        style = str(body.get("style", "other"))
        lora = body.get("lora") if body.get("lora") in self.loras else None
        self._stil(style, lora, body.get("lora_weight"))
        tarif = str(body.get("prompt", "")).strip()[:900] or "game character"
        if style == "pixel" and "pixel" not in tarif.lower():
            tarif = "pixel art, " + tarif
        if lora:
            tarif = f"{tarif}, {self.loras[lora][1]}"
        W, H = 768, 1024
        neg = str(body.get("negative") or "text, watermark, blurry, cropped, frame, border, scenery, landscape, ground shadow, "
                  "cast shadow, deformed, extra limbs, extra arms, extra legs, bad anatomy, floating objects")[:500]
        tek = f"{tarif}, solo, one single character, full body, side view, facing right, profile, isolated on a plain flat solid light gray background"
        iki = (f"two side-by-side pictures of the exact same character, identical outfit and colors, {tarif}, full body, "
               "side view, facing right, isolated on a plain flat solid light gray background")
        dur = pozlar.ciz(pozlar.kareler("bekleme")[0], W, H)
        gri = Image.new("RGB", (224, 224), (128, 128, 128))
        # 1) yandan referans: kullanıcının görseli varsa önce aynı karakterin yandan duruşu çizilir (görsel önden olabilir)
        ref_b64 = body.get("image") or body.get("reference")
        if ref_b64:
            im = Image.open(io.BytesIO(base64.b64decode(str(ref_b64).split(",")[-1]))).convert("RGBA")
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
            im.thumbnail((int(W * 0.9), int(H * 0.88)), Image.LANCZOS)
            k = Image.new("RGBA", (W, H), (200, 200, 200, 255))
            k.alpha_composite(im, ((W - im.width) // 2, int(H * 0.94) - im.height))
            kullanici = k.convert("RGB")
            ref = self._yan_yana(kullanici, Image.new("RGB", (W, H)), dur, iki, neg, seed, 0.7, W, H, steps=25)
        else:
            self.pipe.set_ip_adapter_scale(0.0)
            ref = self.pipe(prompt=tek, negative_prompt=neg, image=dur, num_inference_steps=25, guidance_scale=6.0,
                            width=W, height=H, generator=torch.Generator("cuda").manual_seed(seed), ip_adapter_image=gri,
                            controlnet_conditioning_scale=0.9).images[0]
        t_ref = round(time.time() - t0, 1)
        # 2) kareler (yan yana yöntem)
        kareler = []
        for p in pozlar.kareler(tur, n):
            kareler.append(self._yan_yana(ref, dur, pozlar.ciz(p, W, H), iki, neg, seed, float(body.get("ref_scale", 0.6)), W, H))
        t_kare = round(time.time() - t0 - t_ref, 1)
        # 3) temizlik + hizalama: hepsi aynı kutuyla kırpılır (zıplama/eğilme gibi hareketler korunur)
        kesik = [self._kes(k) for k in kareler] if body.get("auto", True) else [k.convert("RGBA") for k in kareler]
        kutular = [k.getbbox() for k in kesik if k.getbbox()]
        if kutular:
            pad = 6
            x0 = max(0, min(b[0] for b in kutular) - pad); y0 = max(0, min(b[1] for b in kutular) - pad)
            x1 = min(W, max(b[2] for b in kutular) + pad); y1 = min(H, max(b[3] for b in kutular) + pad)
            kesik = [k.crop((x0, y0, x1, y1)) for k in kesik]
        if int(body.get("yon", 1)) < 0:
            kesik = [k.transpose(Image.FLIP_LEFT_RIGHT) for k in kesik]

        def b64(im):
            buf = io.BytesIO(); im.save(buf, format="PNG"); return base64.b64encode(buf.getvalue()).decode()

        r = {"frames": [b64(k) for k in kesik], "reference": b64(ref), "anim": tur, "n": n,
             "seconds": round(time.time() - t0, 2), "sure": {"referans": t_ref, "kareler": t_kare}}
        if body.get("poz"):
            r["poses"] = [b64(pozlar.ciz(p, 192, 256)) for p in pozlar.kareler(tur, n)]
        return r

    @modal.asgi_app()
    def web(self):
        import os

        from fastapi import FastAPI, Header, HTTPException
        from fastapi.middleware.cors import CORSMiddleware

        api = FastAPI()
        api.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])
        key = os.environ.get("SPRITE_KEY", "")

        @api.get("/")
        def health():
            return {"ok": True, "motor": "animator (OpenPose ControlNet + IP-Adapter)", "gpu": "L4", "turler": ANIM_TURLER}

        @api.post("/animate")
        def animate(body: dict, x_sprite_key: str = Header(default="")):
            if key and x_sprite_key != key:
                raise HTTPException(status_code=401, detail="Anahtar yanlış")
            try:
                return self.animate(body)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:  # noqa
                import traceback

                iz = traceback.format_exc()
                print(iz, flush=True)
                raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)[:300]} | {iz[-700:]}")

        return api
