# Yol Haritası — ilerleme

Her gece bir madde (ya da büyük bir maddenin bir parçası) yapılır. ✅ bitti · 🔄 sürüyor · ⬜ sırada

## 0. Görsel kalitesi (öncelikli)
- 🔄 a) İnce ayarlı ana model — aday: `Lykon/dreamshaper-xl-1-0` (lisans: openrail++, ticari kullanım uygun). Karşılaştırma iş akışı: `karsilastir.yml` + `modal/karsilastir.py`.
  - 20 Kasım: 3 deneme yapıldı; deneme motoru kuruldu ama hiç açılmadı (sağlık isteği cevapsız kaldı, konteyner kaydı yok). Canlı motor sorunsuz.
  - Güvenlik için `modal/app.py` canlı sürüme geri alındı. Model seçimi değişikliği e03fb83 + b394d6a commit'lerinde duruyor.
  - Sonraki gece: (1) önce HF'de Lykon deposunun dosya listesini GitHub Actions içinden yazdır (fp16 var mı, unet .bin mi?); (2) deneme motoru için ayrı dosya (modal/deneme.py) kullan, canlı app.py'ye dokunma; (3) `modal container list` / `modal app logs` ile açılış hatasını yakala; olmazsa aday değiştir (ör. fp16 dosyası kesin olan bir openrail++ model).
- ⬜ b) Stile özel LoRA'lar (çizgi film, chibi, karanlık fantastik, HD)
- ⬜ c) İki aşamalı üretim (hi-res fix) + sitede "Ekstra kalite"
- ⬜ d) Yüz düzeltme
- ⬜ e) "En iyisini seç" (estetik/CLIP puanı)

## 1. ⬜ Sipariş sistemi (siparis.yml, AJAN_TOKEN gerekli)
## 2. ⬜ Yapay zekâ ile gerçek animasyon (OpenPose ControlNet + IP-Adapter, /animate)
## 3. ⬜ Tileset (Wang/blob geçişleri, Godot .tres)
## 4. ⬜ Yön seti iyileştirme (arkadan görünüş, 4/8 yön)
## 5. ⬜ Görselden 3D model (.glb)
## 6. ⬜ Ses efekti (.wav, "Ses" sekmesi)
## 7. ⬜ Sonrası: stil LoRA eğitimi, UI kit, kart çerçevesi nadirlik setleri

## Yedekler
- kararli-v3: 2026-11-20 (0a öncesi)

## Gece günlüğü
- 2026-11-20: 0a başladı — karşılaştırma iş akışı eklendi; DreamShaper deneme motoru açılmadı (3/3 deneme hakkı kullanıldı), canlı motor değişmedi.

## Tahmini Modal harcaması (Kasım 2026)
- 19-20 Kasım: ~17 motor kurulumu + ~8 üretim + 3 karşılaştırma denemesi → tahmini 2-4 $ (20 $ sınırının çok altında).
