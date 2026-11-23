# Sprite Atölye — çalışma kuralları

Kullanıcı (Mehmet Ali) ile her zaman **Türkçe** konuş.

## Motor (modal/) tek oturumdan — 23 Kasım kararı
- Modal motoru (`modal/`, `.github/workflows/modal.yml`) aynı anda **yalnızca tek bir oturumdan** değiştirilir.
  Her gönderim motoru yeniden kurar ve tek T4'te deneme üretimi başlatır; iki oturum üst üste gönderince
  testler birbirini bekler, çalışan işler yarıda kesilir, Modal kredisi boşa gider.
- `modal/` altına göndermeden önce: `gh run list --workflow modal.yml -L 3` — çalışan bir kurulum varsa ve
  senin değilse, o oturumun işi bitene kadar `modal/` değiştirme (site, belge, iş akışı işleri serbest).
- Motor değişikliklerini topla, tek gönderimde yolla. Sadece belge/yol haritası değişikliklerinde `[skip ci]`.
- `modal.yml` tek kurulum çalıştırır (concurrency: yeni gönderim eskisini iptal eder).
- Gece görevi (Sprite Atölye — gece geliştirme) de bu kurala uyar: başka bir oturum motorda çalışıyorsa motorsuz (site) işlere geçer.

## Diğer kurallar
- Her gece önce `DERSLER.md`, sonra `YOL_HARITASI.md` okunur.
- Modal web uç noktası 150 sn'yi aşan isteğe 303 döner: uzun işler iş kuyruğuyla (`POST /is/<tür>`, `GET /is/<id>`;
  Actions betiklerinde `modal/motor_istemci.py`).
- Bütçe: aylık 30 $, harcama limiti 0 $.
