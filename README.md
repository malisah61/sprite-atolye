# Sprite Atölye

Ücretsiz oyun asset üreticisi: karakter, düşman, eşya, ikon ve tile üretir; arka planı siler, pixel art'a çevirir, kodla tutarlı animasyon kareleri çıkarır ve Godot/Unity için sprite sheet hazırlar.

**Site:** https://malisah61.github.io/sprite-atolye/

## Sekmeler
- **Üret** — Pollinations (ücretsiz, anahtarsız) ile görsel üretir. Türkçe yazılan açıklama otomatik İngilizceye çevrilir. Ücretsiz katmanda istekler arasında ~15 sn sıra beklenir.
- **Atölye** — arka plan silme, boşluk kırpma, pixel art (boyut + renk sayısı), kontur.
- **Animasyon** — tek sprite'tan bekleme, yürüme, koşma, saldırı, hasar, ölüm, süzülme, dönme kareleri.
- **Sheet** — kareleri tek PNG'de birleştirir; JSON ve Godot 4 `SpriteFrames` (.tres) indirir.
- **Tileset** — iki dikişsiz zemin dokusundan geçiş seti (16'lık köşe/Wang ya da 47'lik blob) üretir; rastgele harita önizlemesi; Godot 4 `TileSet` (.tres, arazi/terrain ayarlı) ve .zip indirir. Tarayıcıda çalışır, motor harcamaz.
- **Galeri** — her şey tarayıcıda (IndexedDB) saklanır; hepsi tek ZIP olarak indirilebilir.

## Yol haritası
1. ✅ Modal GPU motoru (SDXL + pixel-art-xl, T4): https://malisah61--sprite-atolye-motor-web.us-east.modal.run — ~21 sn/görsel (1024px).
2. ✅ Oyun repoları için sipariş sistemi: `assets/siparis.json` → Actions → **Sipariş** (`siparis.yml`) üretir; `"hat": "komando"` ile görsel → 3D (TripoSR) → Quaternius iskeleti → Komando'nun 8 yön × 8 animasyon sprite sayfası. Ayrıntı: `siparis/`.
3. Tileset (kenar/köşe parçaları), yön setleri (4/8 yön), Godot paket dışa aktarma.

## Yapı
Saf HTML/CSS/JS, derleme yok. `main` dalına her push'ta GitHub Actions siteyi Pages'e yayınlar.
