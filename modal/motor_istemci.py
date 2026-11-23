"""Motor istemcisi (Actions betikleri için): uzun işler iş kuyruğuyla.

Modal web uç noktası 150 sn'yi aşan isteğe 303 yönlendirme döner; urllib bunu üst üste izleyip
"redirect loop" hatasıyla düşüyordu (23 Kasım: uret.yml 11 dk sonra başarısız). Bu yüzden:
POST /is/<tür> → {"is": id}, sonra GET /is/<id> yoklanır. Kuyruk yoksa (eski motor) doğrudan çağrı.

    from motor_istemci import cagir
    d = cagir(url, "generate", govde, anahtar)
"""
import json
import time
import urllib.error
import urllib.request


def _istek(url, veri, anahtar, zaman):
    h = {"X-Sprite-Key": anahtar}
    if veri is not None:
        h["Content-Type"] = "application/json"
        veri = json.dumps(veri).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=veri, headers=h), timeout=zaman))


def cagir(url, tur, govde, anahtar, sure=1500, deneme=3):
    kok = url.rstrip("/")
    for i in range(deneme):
        try:
            is_id = _istek(f"{kok}/is/{tur}", govde, anahtar, 600)["is"]
            break
        except urllib.error.HTTPError as e:
            if e.code in (404, 405):  # eski motor: kuyruk yok
                return _istek(f"{kok}/{tur}", govde, anahtar, 900)
            if e.code == 401:
                raise
            print(f"iş başlatılamadı ({i + 1}/{deneme}): HTTP {e.code}", flush=True)
        except Exception as e:  # noqa — soğuk başlangıçta düşebilir
            print(f"iş başlatılamadı ({i + 1}/{deneme}): {e}", flush=True)
        time.sleep(15)
    else:
        raise SystemExit("motor iş kabul etmedi")
    bitis, hata = time.time() + sure, 0
    while time.time() < bitis:
        time.sleep(4)
        try:
            d = _istek(f"{kok}/is/{is_id}", None, anahtar, 120)
            hata = 0
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise SystemExit("iş kayboldu (motor yeniden başladı)")
            hata += 1
        except Exception:  # noqa
            hata += 1
        else:
            if d.get("durum") == "bitti":
                return d["sonuc"]
            if d.get("durum") == "hata":
                raise SystemExit(f"motor hatası: {d.get('detay')}")
            continue
        if hata > 8:
            raise SystemExit("motora ulaşılamıyor")
    raise SystemExit("zaman aşımı")
