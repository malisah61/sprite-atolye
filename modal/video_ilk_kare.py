"""Video denemesi için ilk kare: canlı motorla (DreamShaper + çizgi film LoRA + IP-Adapter referans) sahne görseli üretir.
Kullanım: python3 modal/video_ilk_kare.py sahneler.json [referans.png] → ilk_kare_1.png, ilk_kare_2.png, ...
Her sahnede "ilk" alanı = o sahnenin ilk karesinin tarifi (aynı karakter tarifi + referans → tutarlı karakter)."""
import base64
import json
import os
import sys
import urllib.request

urllib.request.HTTPRedirectHandler.max_repeats = 6
urllib.request.HTTPRedirectHandler.max_redirections = 8
URL = os.environ["MOTOR_URL"].rstrip("/")
KEY = os.environ.get("SPRITE_KEY", "")
sahneler = json.load(open(sys.argv[1]))
body = { "seed": int(os.environ.get("SEED", "42")), "n": 1, "width": 1216, "height": 704,
        "style": "other", "auto": False, "lora": "cartoon",
        "negative": "text, watermark, blurry, multiple characters, character sheet, reference sheet, multiple views, duplicate, frame, border"}
if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
    body["reference"] = base64.b64encode(open(sys.argv[2], "rb").read()).decode()
    body["ref_scale"] = 0.55
print(urllib.request.urlopen(URL + "/", timeout=600).read().decode()[:200], flush=True)
for i, s in enumerate(sahneler, 1):
    body["prompt"] = s["ilk"]
    req = urllib.request.Request(URL + "/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Sprite-Key": KEY})
    d = json.load(urllib.request.urlopen(req, timeout=900))
    open(f"ilk_kare_{i}.png", "wb").write(base64.b64decode(d["images"][0]))
    print(f"ilk kare {i} hazır: GPU {d['seconds']} sn", flush=True)
