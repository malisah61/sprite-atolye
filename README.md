# Sprite Atölye

Ücretsiz oyun asset üreticisi: karakter, düşman, eşya, ikon ve tile üretir; arka planı siler, pixel art'a çevirir, kodla tutarlı animasyon kareleri çıkarır ve Godot/Unity için sprite sheet hazırlar.

**Site:** https://malisah61.github.io/sprite-atolye/

## Sekmeler
- **Üret** — Pollinations (ücretsiz, anahtarsız) ile görsel üretir. Türkçe yazılan açıklama otomatik İngilizceye çevrilir. Ücretsiz katmanda istekler arasında ~15 sn sıra beklenir.
- **Atölye** — arka plan silme, boşluk kırpma, pixel art (boyut + renk sayısı), kontur.
- **Animasyon** — tek sprite'tan bekleme, yürüme, koşma, saldırı, hasar, ölüm, süzülme, dönme kareleri.
- **Sheet** — kareleri tek PNG'de birleştirir; JSON ve Godot 4 `SpriteFrames` (.tres) indirir.
- **Galeri** — her şey tarayıcıda (IndexedDB) saklanır; hepsi tek ZIP olarak indirilebilir.

## Yol haritası
1. Modal üzerinde kendi GPU motorumuz (pixel art LoRA, karakter tutarlılığı) — `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` secret'ları ile otomatik kurulum.
2. Oyun repoları için sipariş sistemi: `assets/siparis.json` → GitHub Actions üretir → repoya ekler.
3. Tileset (kenar/köşe parçaları), yön setleri (4/8 yön), Godot paket dışa aktarma.

## Yapı
Saf HTML/CSS/JS, derleme yok. `main` dalına her push'ta GitHub Actions siteyi Pages'e yayınlar.
