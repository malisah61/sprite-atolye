# Yol Haritası — ilerleme

Her gece bir madde (ya da büyük bir maddenin bir parçası) yapılır. ✅ bitti · 🔄 sürüyor · ⬜ sırada

## 0. Görsel kalitesi (öncelikli)
- ✅ a) İnce ayarlı ana model → **Lykon/dreamshaper-xl-1-0** (openrail++, ticari kullanım serbest). Karşılaştırma: `karsilastir.yml` (deneme motoru `modal run` ile, canlıya dokunmadan). 20 Kasım sonucu: pixel zombi ve HD aslanda belirgin daha detaylı, kılıç benzer, çizgi film kadında iki model de karakter sayfası üretti (negatife "reference sheet, model sheet, multiple poses" eklendi). pixel-art-xl LoRA ve IP-Adapter yeni modelle çalışıyor. Açılmama sebebi: DreamShaper'ın DEIS zamanlayıcı ayarı → DPM++ 2M Karras zorlandı. Eskiye dönüş: app.py'de BASE satırı.
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
- kararli-v4: 2026-11-20 (DreamShaper'a geçiş öncesi)

## Gece günlüğü
- 2026-11-20: 0a başladı — karşılaştırma iş akışı eklendi; DreamShaper deneme motoru açılmadı (3/3 deneme hakkı kullanıldı), canlı motor değişmedi.
- 2026-11-20 (gündüz, elle başlatıldı): sebep bulundu (zamanlayıcı), karşılaştırma tamamlandı, ana model DreamShaper XL'e geçti.

## Tahmini Modal harcaması (Kasım 2026)
- 19-20 Kasım: ~17 motor kurulumu + ~8 üretim + 3 karşılaştırma denemesi → tahmini 2-4 $ (20 $ sınırının çok altında).
