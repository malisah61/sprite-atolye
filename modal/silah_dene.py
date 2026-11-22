"""Fazladan silah algılayıcı denemesi (GPU'suz, Actions CPU): CLIPSeg ile 'weapon'/'sword'/'axe' bölgeleri,
bağlı parça sayıları ve CLIP puanları. Kullanım: python3 modal/silah_dene.py klasor"""
import glob
import sys

import numpy as np
import torch
from PIL import Image
from scipy import ndimage
from transformers import CLIPModel, CLIPProcessor, CLIPSegForImageSegmentation, CLIPSegProcessor

sp = CLIPSegProcessor.from_pretrained("CIDAS/clipseg-rd64-refined")
sm = CLIPSegForImageSegmentation.from_pretrained("CIDAS/clipseg-rd64-refined").eval()
cp = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
cm = CLIPModel.from_pretrained("openai/clip-vit-large-patch14").eval()


def gri(im):
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, (128, 128, 128, 255)); bg.alpha_composite(im)
    return bg.convert("RGB")


def maske(im, ad):
    with torch.no_grad():
        inp = sp(text=[ad], images=[im], return_tensors="pt")
        lg = sm(**inp, interpolate_pos_encoding=True).logits
    pr = torch.sigmoid(lg).squeeze().numpy()
    return np.array(Image.fromarray((pr * 255).astype(np.uint8)).resize(im.size, Image.BILINEAR)) / 255.0


def pref(im, a, b):
    with torch.no_grad():
        inp = cp(text=[a, b], images=im, return_tensors="pt", padding=True)
        return cm(**inp).logits_per_image.softmax(-1)[0, 0].item()


for f in sorted(glob.glob(sys.argv[1] + "/*.png")):
    im = gri(Image.open(f))
    sat = []
    for ad in ["weapon", "sword", "axe", "sword blade"]:
        m = maske(im, ad)
        for esik in (0.3, 0.4, 0.5):
            a = m > esik
            lab, n = ndimage.label(a)
            sz = sorted(np.bincount(lab.ravel())[1:] / a.size, reverse=True) if n else []
            buyuk = [round(float(x) * 100, 2) for x in sz if x > 0.002][:4]
            sat.append(f"{ad}@{esik}: {buyuk}")
    p1 = pref(im, "a warrior holding a single axe", "a warrior holding an axe and a sword")
    print(f"\n== {f.split('/')[-1]}  CLIP tek-balta={p1:.2f}")
    print("   " + " | ".join(sat))
