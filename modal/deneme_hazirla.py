"""Deneme motoru dosyası hazırlar: modal/app.py'yi (canlı motor) KOPYALAR, sadece model adını, uygulama adını
ve modelin dosya biçimine göre indirme/yükleme ayarlarını değiştirir → modal/deneme_app.py.
Canlı app.py'ye dokunulmaz. Kullanım: python3 modal/deneme_hazirla.py <hf-model>"""
import os
import re
import sys

from huggingface_hub import list_repo_files

model = sys.argv[1]
files = list_repo_files(model)
OZET = os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null")
print(f"== {model}: {len(files)} dosya")
for f in files:
    if "/" in f and f.split("/")[0] in ("unet", "text_encoder", "text_encoder_2", "vae") or "/" not in f:
        print("  ", f)

parcalar = ["unet", "text_encoder", "text_encoder_2"]


def var(p, uzanti):
    return any(f.startswith(p + "/") and f.endswith(uzanti) for f in files)


fp16 = all(var(p, ".fp16.safetensors") for p in parcalar)
st = all(var(p, ".safetensors") and any(f.startswith(p + "/") and f.endswith(".safetensors") and ".fp16." not in f for f in files) for p in parcalar)
eksik = [p for p in parcalar + ["tokenizer", "tokenizer_2", "scheduler"] if not any(f.startswith(p + "/") for f in files)]
if eksik:
    msg = f"❌ {model} diffusers formatında değil, eksik klasörler: {eksik}"
    print(msg); open(OZET, "a").write(msg + "\n")
    sys.exit(1)

if fp16:
    desen, variant, ignore = "*.fp16.safetensors", '"fp16"', "[]"
elif st:
    desen, variant, ignore = "*.safetensors", "None", '["*.fp16.*"]'
else:  # sadece .bin
    desen, variant, ignore = "*.bin", "None", '["*.fp16.*"]'
msg = f"{model}: biçim = {desen}, variant = {variant}"
print(msg); open(OZET, "a").write(f"- {msg}\n")

s = open("modal/app.py").read()
s2 = s
s2 = re.sub(r'^APP_NAME = .*$', 'APP_NAME = "sprite-atolye-deneme"', s2, count=1, flags=re.M)
s2 = re.sub(r'^BASE = .*$', f'BASE = "{model}"', s2, count=1, flags=re.M)
s2 = s2.replace('"unet/*.fp16.safetensors", "text_encoder*/*.fp16.safetensors",',
                f'"unet/{desen}", "text_encoder*/{desen}",')
s2 = s2.replace('"tokenizer*/*", "scheduler/*", "model_index.json"],\n    )',
                f'"tokenizer*/*", "scheduler/*", "model_index.json"],\n        ignore_patterns={ignore},\n    )')
s2 = s2.replace('torch_dtype=torch.float16, variant="fp16", use_safetensors=True',
                f'torch_dtype=torch.float16, variant={variant}, use_safetensors={"False" if desen == "*.bin" else "True"}')
s2 = s2.replace("        self.rb = new_session(\"isnet-general-use\")\n",
                "        self.rb = new_session(\"isnet-general-use\")\n        print('[deneme motor] hazır', flush=True)\n", 1)
# İnce ayarlı modellerin bir kısmı başka zamanlayıcı (ör. DEIS) ayarıyla gelir: canlı motorla aynı DPM++ 2M Karras'ı zorla
s2 = s2.replace("pipe.scheduler.config, use_karras_sigmas=True\n",
                "pipe.scheduler.config, use_karras_sigmas=True, algorithm_type=\"dpmsolver++\", solver_type=\"midpoint\",\n"
                "            final_sigmas_type=\"zero\", timestep_spacing=\"leading\", steps_offset=1\n", 1)
# `modal run` ile çalıştırmak için: doğrudan çağrılabilir üretim metodu + yerel giriş noktası.
# (modal run konteyner kayıtlarını Actions çıktısına akıtır ve iş bitince uygulamayı kendisi kapatır.)
s2 = s2.replace("    @modal.asgi_app()\n", '''    @modal.method()
    def uret(self, b):
        return self._run(b["prompt"], b["negative"], int(b["seed"]), int(b.get("n", 1)), int(b["width"]), int(b["height"]),
                         b.get("style", "pixel"), False, bool(b.get("auto", False)), False,
                         self._ref(b.get("reference")), float(b.get("ref_scale", 0.6)), False)

    @modal.asgi_app()
''', 1)
s2 += '''

@app.local_entrypoint()
def karsilastir_yerel():
    import os as _os
    import sys as _sys

    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    import karsilastir

    m = Motor()
    karsilastir.calistir(lambda body: m.uret.remote(body))
'''
if "def uret(self, b)" not in s2:
    print("❌ asgi_app bulunamadı"); sys.exit(1)
if f'BASE = "{model}"' not in s2 or f'"unet/{desen}"' not in s2 or f"variant={variant}" not in s2:
    print("❌ app.py beklenen biçimde değil, deneme dosyası hazırlanamadı"); sys.exit(1)
open("modal/deneme_app.py", "w").write(s2)
print("modal/deneme_app.py hazır")
