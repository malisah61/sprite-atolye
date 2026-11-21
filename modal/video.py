"""Sprite Atölye — Video motoru (deneme).

Wan 2.2 TI2V-5B (Apache-2.0: ücretsiz, ticari kullanım serbest) ile görselden hareketli video.
Ana motordan ayrı bir uygulama: L4 GPU (24 GB), aynı anda tek GPU, iş bitince kapanır.

Deneme: `modal run modal/video.py --ilk ilk_kare.png --sahneler sahneler.json`
  → her sahne bir klip; her klibin son karesi bir sonrakinin ilk karesi (kesintisiz hareket)
  → video_sahne_N.mp4 + video_tam.mp4
"""
import modal

APP_NAME = "sprite-atolye-video"
WAN = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
FPS = 24


def indir():
    from huggingface_hub import snapshot_download

    snapshot_download(WAN)


image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "torch==2.6.0",
        "diffusers==0.35.1",
        "transformers==4.53.3",
        "accelerate==1.9.0",
        "safetensors==0.5.3",
        "huggingface_hub==0.34.4",
        "sentencepiece",
        "ftfy",
        "imageio==2.37.0",
        "imageio-ffmpeg==0.6.0",
        "pillow==11.0.0",
        "numpy<2.3",
    )
    .run_function(indir, timeout=3600)
)

app = modal.App(APP_NAME, image=image)

NEG = ("blurry, distorted, deformed, disfigured, extra limbs, extra fingers, bad anatomy, static, still image, frozen, "
       "low quality, worst quality, jpeg artifacts, watermark, text, subtitles, flicker, morphing face, ugly")


@app.cls(gpu="L4", memory=32768, timeout=3600, scaledown_window=60, max_containers=1)
class Video:
    @modal.enter()
    def yukle(self):
        import time

        import torch
        from diffusers import AutoencoderKLWan, WanImageToVideoPipeline

        t = time.time()
        vae = AutoencoderKLWan.from_pretrained(WAN, subfolder="vae", torch_dtype=torch.float32)
        self.pipe = WanImageToVideoPipeline.from_pretrained(WAN, vae=vae, torch_dtype=torch.bfloat16)
        # 24 GB'a sığması için parçalar sırayla GPU'ya alınır (metin kodlayıcı büyük)
        self.pipe.enable_model_cpu_offload()
        print(f"[video] model yüklendi: {round(time.time() - t)} sn · ayarlar: "
              f"expand_timesteps={getattr(self.pipe.config, 'expand_timesteps', None)}", flush=True)

    @modal.method()
    def klip(self, ilk_png: bytes, prompt: str, seed: int = 42, width: int = 832, height: int = 480,
             kare: int = 121, adim: int = 30, guidance: float = 5.0):
        """Bir klip üretir → (mp4 baytları, son kare png baytları, saniye)."""
        import io
        import tempfile
        import time

        import torch
        from diffusers.utils import export_to_video
        from PIL import Image, ImageOps

        t = time.time()
        im = Image.open(io.BytesIO(ilk_png)).convert("RGB")
        im = ImageOps.fit(im, (width, height), Image.LANCZOS)  # en-boy oranını koruyarak kırp
        g = torch.Generator("cpu").manual_seed(seed)
        kareler = self.pipe(image=im, prompt=prompt, negative_prompt=NEG, height=height, width=width,
                            num_frames=kare, num_inference_steps=adim, guidance_scale=guidance,
                            generator=g, output_type="pil").frames[0]
        with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
            export_to_video(kareler, f.name, fps=FPS)
            mp4 = open(f.name, "rb").read()
        buf = io.BytesIO()
        kareler[-1].save(buf, format="PNG")
        sn = round(time.time() - t, 1)
        print(f"[video] klip hazır: {len(kareler)} kare, {sn} sn", flush=True)
        return mp4, buf.getvalue(), sn


@app.local_entrypoint()
def dene(ilk: str = "ilk_kare.png", sahneler: str = "sahneler.json", seed: int = 42):
    import json
    import os
    import subprocess

    ozet = open(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"), "a")
    liste = json.load(open(sahneler))
    v = Video()
    son = open(ilk, "rb").read()
    dosyalar, toplam = [], 0.0
    for i, s in enumerate(liste, 1):
        mp4, son, sn = v.klip.remote(son, s["prompt"], seed + i, kare=int(s.get("kare", 121)))
        ad = f"video_sahne_{i}.mp4"
        open(ad, "wb").write(mp4)
        open(f"video_sahne_{i}_son.png", "wb").write(son)
        dosyalar.append(ad)
        toplam += sn
        msg = f"Sahne {i}: {sn} sn GPU — {s['prompt'][:80]}"
        print(msg, flush=True); ozet.write(f"- {msg}\n")
    # klipleri tek videoda birleştir (yerelde ffmpeg)
    open("liste.txt", "w").write("".join(f"file '{d}'\n" for d in dosyalar))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "liste.txt",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "video_tam.mp4"], check=True)
    maliyet = toplam / 3600 * 0.80  # L4 ≈ 0.80 $/saat (yaklaşık)
    msg = f"Toplam GPU {round(toplam)} sn ≈ {maliyet:.2f} $ (yükleme hariç) · video_tam.mp4 hazır"
    print(msg); ozet.write(f"- {msg}\n")
