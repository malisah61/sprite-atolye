# Yol Haritası — ilerleme

Her gece bir madde (ya da büyük bir maddenin bir parçası) yapılır. ✅ bitti · 🔄 sürüyor · ⬜ sırada

## 0. Görsel kalitesi (öncelikli)
- ✅ a) İnce ayarlı ana model → **Lykon/dreamshaper-xl-1-0** (openrail++, ticari kullanım serbest). Karşılaştırma: `karsilastir.yml` (deneme motoru `modal run` ile, canlıya dokunmadan). 20 Kasım sonucu: pixel zombi ve HD aslanda belirgin daha detaylı, kılıç benzer, çizgi film kadında iki model de karakter sayfası üretti (negatife "reference sheet, model sheet, multiple poses" eklendi). pixel-art-xl LoRA ve IP-Adapter yeni modelle çalışıyor. Açılmama sebebi: DreamShaper'ın DEIS zamanlayıcı ayarı → DPM++ 2M Karras zorlandı. Eskiye dönüş: app.py'de BASE satırı.
- ✅ b) Stile özel LoRA'lar — 21 Kasım: motorda `"lora"` alanı (tetik kelimesi otomatik), sitede "Stil güçlendirici" kutusu (varsayılan açık).
  Karşılaştırma (`karsilastir.yml`, modul=lora_karsilastir, seed 42) sonucu:
  - çizgi film → `issaccyj/lora-sdxl-cartoonillustration` 0.8 ✅ (karakter sayfası sorunu çözüldü, tek temiz figür) — sitede AÇIK
  - chibi → `strkyyy/anime-chibi` 0.75 ✅ (gerçek büyük kafa oranı) — sitede AÇIK
  - karanlık → `Geroloq/darkfantasy_style_LoRA` ⚠️ 0.8'de arka planı koyu/dokulu yapıyor; motorda 0.5 varsayılan, sitede KAPALI (ileride 0.5 + temizlik denenecek)
  - HD → `ntc-ai/...extremely-detailed` ❌ fark yok denecek kadar az; `ntc-ai/...cartoon` ❌ karakter sayfası sürdü → elendi
  - Lisanslar model kartlarından kontrol edildi (`lora_ara.yml` kart: kipi): openrail++.
  Eski aday notları:
  - çizgi film: `issaccyj/lora-sdxl-cartoonillustration` (openrail++), `ntc-ai/SDXL-LoRA-slider.cartoon` (mit, kaydırıcı)
  - chibi: `strkyyy/anime-chibi` (openrail++)
  - karanlık fantastik: `Geroloq/darkfantasy_style_LoRA` (openrail++)
  - "Muapi/..." depoları Civitai'den yeniden yüklenmiş; lisans etiketi asıl yazarın şartlarını yansıtmayabilir → kullanma. Oyun/marka adı geçenler (diablo, nendoroid) → kullanma.
  - Sonraki adım: deneme motoruna (karsilastir.yml benzeri) LoRA'ları ekleyip stil başına örnek üret, bak, ağırlık seç.
- Bilinen eski sorun: test_motor'daki boyayarak düzenleme testinde (üst %25 maske) kafa siliniyor — eski modelde de vardı; maske/temizlik ayarına bakılacak.
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
- kararli-v5: 2026-11-21 (stil LoRA'ları öncesi)

## Gece günlüğü
- 2026-11-20: 0a başladı — karşılaştırma iş akışı eklendi; DreamShaper deneme motoru açılmadı (3/3 deneme hakkı kullanıldı), canlı motor değişmedi.
- 2026-11-20 (gündüz, elle başlatıldı): sebep bulundu (zamanlayıcı), karşılaştırma tamamlandı, ana model DreamShaper XL'e geçti; canlı testler geçti. LoRA aday listesi çıkarıldı (0b hazırlığı).

- 2026-11-21 (gece): 0b — stil LoRA karşılaştırması (1 deneme motoru, 9 görsel), çizgi film + chibi LoRA'ları canlıya alındı, sitede "Stil güçlendirici".

## Tahmini Modal harcaması (Kasım 2026)
- 19-20 Kasım: ~17 motor kurulumu + ~8 üretim + 3 karşılaştırma denemesi → tahmini 2-4 $ (20 $ sınırının çok altında).
- 20 Kasım akşamı (gündüz oturumu): ~4 kurulum+test daha → +~1 $
- 21 Kasım: 1 LoRA karşılaştırması + 1 kurulum/test → +~0.5 $. Ay toplamı tahmini 4-6 $.
