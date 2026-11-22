"""Görselden 3D model (TripoSR, MIT lisans; stabilityai/TripoSR). CPU'da da çalışır (GitHub Actions).
Kullanım: python3 uc_boyut/gorselden_3d.py giris.png cikis.glb [cozunurluk]
Giriş: arka planı silinmiş (RGBA) ya da düz arka planlı karakter görseli."""
import sys
import time

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, "TripoSR")
from tsr.system import TSR  # noqa: E402
from tsr.utils import resize_foreground  # noqa: E402

giris, cikis = sys.argv[1], sys.argv[2]
coz = int(sys.argv[3]) if len(sys.argv) > 3 else 256
t0 = time.time()
model = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
model.renderer.set_chunk_size(8192)
model.to("cpu")
print(f"model yüklendi {time.time() - t0:.0f} sn", flush=True)

im = Image.open(giris).convert("RGBA")
if np.array(im)[..., 3].min() == 255:  # alfa yoksa: arka planı rembg ile sil
    import rembg
    im = rembg.remove(im.convert("RGB")).convert("RGBA")
im = resize_foreground(im, 0.85)
a = np.array(im).astype(np.float32) / 255.0
rgb = a[..., :3] * a[..., 3:4] + (1 - a[..., 3:4]) * 0.5
im = Image.fromarray((rgb * 255).astype(np.uint8))
im.save(cikis.replace(".glb", "_giris.png"))

t1 = time.time()
with torch.no_grad():
    kod = model([im], device="cpu")
    try:
        mesh = model.extract_mesh(kod, True, resolution=coz)[0]
    except TypeError:
        mesh = model.extract_mesh(kod, resolution=coz)[0]
print(f"3D çıkarıldı {time.time() - t1:.0f} sn · {len(mesh.vertices)} köşe, {len(mesh.faces)} yüz", flush=True)
mesh.export(cikis)
mesh.export(cikis.replace(".glb", ".ply"))
