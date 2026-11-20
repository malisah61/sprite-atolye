"""HuggingFace'te ticari kullanıma uygun lisanslı SDXL LoRA'larını arar (motor/kredi harcamaz).
Kullanım: python3 modal/lora_ara.py "cartoon,chibi,dark fantasy,painterly" """
import os
import sys

from huggingface_hub import HfApi

UYGUN = {"openrail++", "apache-2.0", "mit", "creativeml-openrail-m", "openrail", "cc-by-4.0", "cc0-1.0", "bsd-3-clause"}
api = HfApi()
OZET = os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null")
out = open(OZET, "a")
if sys.argv[1].startswith("kart:"):
    # kart:repo1,repo2 → model kartlarını (lisans, tetik kelimesi, açıklama) ve dosyaları yazdır
    from huggingface_hub import ModelCard
    for r in sys.argv[1][5:].split(","):
        r = r.strip()
        print(f"\n======== {r}")
        try:
            info = api.model_info(r)
            print("dosyalar:", [s.rfilename for s in info.siblings])
            print("etiketler:", info.tags)
            print(ModelCard.load(r).content[:2500])
        except Exception as e:  # noqa
            print("HATA:", e)
    sys.exit(0)
for kelime in [k.strip() for k in sys.argv[1].split(",") if k.strip()]:
    out.write(f"\n### {kelime}\n| model | lisans | indirme | dosyalar |\n|---|---|---|---|\n")
    print(f"\n=== {kelime}")
    bulunan = 0
    for m in api.list_models(search=kelime, filter=["lora", "base_model:adapter:stabilityai/stable-diffusion-xl-base-1.0"],
                             sort="downloads", limit=40, cardData=True):
        lic = None
        try:
            lic = (m.card_data or {}).get("license")
        except Exception:  # noqa
            pass
        if isinstance(lic, list):
            lic = ",".join(lic)
        if str(lic).lower() not in UYGUN:
            continue
        try:
            files = [s.rfilename for s in api.model_info(m.id, files_metadata=False).siblings if s.rfilename.endswith(".safetensors")]
        except Exception:  # noqa
            files = []
        satir = f"| {m.id} | {lic} | {m.downloads} | {', '.join(files[:3])} |"
        print(satir); out.write(satir + "\n")
        bulunan += 1
        if bulunan >= 8:
            break
