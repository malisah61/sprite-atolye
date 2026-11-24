# Yol Haritası — ilerleme

Her gece bir madde (ya da büyük bir maddenin bir parçası) yapılır. ✅ bitti · 🔄 sürüyor · ⬜ sırada

**Her gece önce `DERSLER.md` okunur**; yeni görülen ve tekrar eden hatalar oraya ve `modal/app.py` → `DERSLER`'e eklenir (kullanıcı isteği, 22 Kasım: "sorunları tekrarlama, öğrensin").

## 0. Görsel kalitesi (öncelikli)
- ✅ f) **Yeni ana çizim motoru: Qwen-Image + Lightning** (24 Kasım, kullanıcıyla; "Gemini gibi hızlı ve anlayan"). Denenenler: FLUX.1-schnell (HF girişi istiyor, inmedi), Z-Image-Turbo (Apache-2.0; tek figür iyi ama fil-kediyi yine fil çizdi), Qwen-Image (Apache-2.0, 20B; vampir-örümcek ve fil-kedi doğru, çizgi film kadında karakter sayfası yok). Süre: görsel başına ~20 sn (parça parça kipte) vs SDXL site ayarlarıyla 80-165 sn; maliyet ~0,011 $/görsel. Canlıda `Ressam` sınıfı (L40S): Lightning LoRA gövdeye birleştirilir + float8 → hepsi GPU'da. Sitede "Çizim motoru" seçimi (varsayılan Qwen), tarif yazılmaya başlanınca motor önceden uyandırılır. Pixel'de Qwen daha sade çiziyor; eski motor seçilebilir.
- ✅ a) İnce ayarlı ana model → **Lykon/dreamshaper-xl-1-0** (openrail++, ticari kullanım serbest). Karşılaştırma: `karsilastir.yml` (deneme motoru `modal run` ile, canlıya dokunmadan). 20 Kasım sonucu: pixel zombi ve HD aslanda belirgin daha detaylı, kılıç benzer, çizgi film kadında iki model de karakter sayfası üretti (negatife "reference sheet, model sheet, multiple poses" eklendi). pixel-art-xl LoRA ve IP-Adapter yeni modelle çalışıyor. Açılmama sebebi: DreamShaper'ın DEIS zamanlayıcı ayarı → DPM++ 2M Karras zorlandı. Eskiye dönüş: app.py'de BASE satırı.
- ✅ b) Stile özel LoRA'lar — 21 Kasım: motorda `"lora"` alanı (tetik kelimesi otomatik), sitede "Stil güçlendirici" kutusu (varsayılan açık).
  Karşılaştırma (`karsilastir.yml`, modul=lora_karsilastir, seed 42) sonucu:
  - çizgi film → `issaccyj/lora-sdxl-cartoonillustration` 0.8 ✅ (stil daha temiz; seed 42 karşılaştırmasında tek figür verdi) — sitede AÇIK. ⚠️ Ama canlı testte (farklı tarif metni) yine 3 görünüşlü karakter sayfası çıktı → LoRA bu sorunu tek başına çözmüyor.
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
- Açık sorun (21 Kasım): çizgi film kadın tarifinde ara ara karakter sayfası (aynı kişi 3 açıdan). Öneri: temizlikten sonra birden fazla büyük figür varsa otomatik yeniden üret / en büyük figürü al. Motorsuz (site) de yapılabilir.
- Bilinen eski sorun: test_motor'daki boyayarak düzenleme testinde (üst %25 maske) kafa siliniyor — eski modelde de vardı; maske/temizlik ayarına bakılacak.
- ✅ c) İki aşamalı üretim (hi-res fix) — 22 Kasım gece: motorda `"hires": true` (1.5x büyüt, uzun kenar en fazla 1536, img2img 0.35, 30×0.35≈11 adım; pixel ve dikişsiz dokuda kapalı). Sitede "Ekstra kalite" kutusu (varsayılan AÇIK; HD / çizgi film / karanlık). Ölçüm (T4, 832×1216 HD aslan): kapalı 23,7 sn → açık 42 sn, ek ~18 sn ≈ **0,003 $/görsel**. Sonuç: yüz/göz ve zırh detayı belirgin daha net, kompozisyon aynı. `uret.yml`'ye `ekstra` girdisi.
  - Yan bulgu: temizlik baltayı ve eli siliyordu → arka plan silme BiRefNet-lite'a geçti (bkz. DERSLER.md); GPU'suz hata ayıklama için `temizlik_dene.yml`. Canlı test: balta + el artık korunuyor; BiRefNet CPU'da görsel başına ~10-14 sn ekliyor (motor cpu=4). Not: test_motor'daki boyama testinde kafa silinmesi sürüyor (eski sorun).
- ✅ d) Yüz düzeltme — 23 Kasım gece: motorda `"yuz": true` → CLIPSeg "face" haritasında en güçlü bölge bulunur, 2.2x çevresi kare kırpılıp 1024'e büyütülür, img2img 0.4 ile ("detailed face, clear expressive eyes...") yeniden çizilir, yumuşak maske + kenara doğru sönen pencereyle geri yapıştırılır. Hi-res'ten sonra çalışır; pixel, doku ve arkadan görünüşte kapalı; yüz zaten büyükse (kırpıntı ≥ 820 px) atlanır. Sitede "Yüz düzeltme" kutusu (karakter/düşman, varsayılan AÇIK); `uret.yml`'ye `yuz` girdisi.
  - Test (`test_motor` → yüz düzeltme): çizgi film kadında **iki gözün farklı renk/biçimde çizilmesi düzeldi** (simetrik, aynı renk iris); HD Alman nöbetçide göz/yüz hatları biraz daha net, dikiş yok (hafif daha doygun ten). Ek süre ~5-8 sn/görsel ≈ 0,001 $.
  - Hata bulundu/düzeltildi: kare 1024 görselde ekstra kalite (1536²) T4'te 500 veriyordu → hi-res toplam piksel ≤1,65 MP; motor hataları artık ayrıntılı. Sonra kare portreler sorunsuz üretildi (1288 px).
  - Yan düzeltme: sitede "tüfekli asker", "kılıçlı şövalye" gibi tarifler artık eşya değil karakter sayılıyor (otomatik tür).
- ✅ e) "En iyisini seç" — 22 Kasım gece (kullanıcı isteğiyle öne alındı): motor her görsele "puan" (CLIP tarif uyumu + varsa ders kontrolü) veriyor, n>1'de en iyisini başa alıyor; sitede aynı üretimin adayları bitince puana göre sıralanıyor, en iyisi "⭐ en iyi" ve sarı çerçeveyle işaretleniyor, her kartta "uyum %". Ayrıca "tek silah" dersi (bkz. DERSLER.md). Canlı test (aslan, seed 42): taslak puanları [1.0, 0.5, 0.5, 0.0] → kılıçsız taslak seçildi, fazladan kılıç yok, balta sağlam; boş kalan ele model kalkan koydu (anatomik hata değil). Bedel: taslak seçimi görsel başına ~+45 sn T4 (≈0,007 $), sadece silahlı karakter tariflerinde.

## V. 🔄 Video / hareketli çizgi film (kullanıcı isteği, 21 Kasım)
- Model: **Wan 2.2 TI2V-5B** (Apache-2.0, ücretsiz, ticari kullanım serbest), ayrı uygulama `sprite-atolye-video` (L4, max 1 GPU, 60 sn'de kapanır). Deneme: `video_dene.yml`.
- 21 Kasım ilk deneme: ilk kare kendi motorumuzla (çizgi film LoRA + referans), 3 sahne × 5 sn (832×480, 24 fps), son kare → sonraki sahnenin ilk karesi.
  - Süre: klip başına ~6,5 dk GPU (30 adım) ≈ 0,09 $/klip; 15 sn video ≈ 0,26 $ GPU (+ yükleme/kurulum ≈ 0,1 $).
  - Sonuç: 1. sahne (yürüme) çok iyi — gerçek akıcı hareket, stil korunuyor. Zincirleme sahnelerde kalite düşüyor: 2. sahnede renkler aşırı doygun, arka plan bulanık; 3. sahnede yüz bozuluyor, kılıç efektleri tuhaf.
  - Düzeltme fikirleri (sıradaki): (1) her sahnenin ilk karesini son kareden değil, kendi motorumuzla taze çiz (referans = karakter, IP-Adapter) ya da son kareye renk eşitleme + hafif SDXL img2img "tazeleme"; (2) adım 30→40; (3) kılıç gibi nesneleri ilk karede zaten çiz (model yoktan nesne çıkarırken bozuluyor).
- 21 Kasım 2. deneme (sabit kamera, her sahne kendi temiz ilk karesinden, 40 adım, paralel GPU): **belirgin daha iyi** — kamera sabit, renkler doğal, zincir bozulması yok. Klip ~8,3 dk GPU ≈ 0,11 $; 15 sn ≈ 0,33 $ (+ yükleme). Kalan kusurlar: 3. sahnede saç rüzgârda aşırı uçuşuyor; sahneler arası kıyafet ufak farklı (1. sahnede şort). Paralellik: 3 istenen GPU'nun 2'si aynı anda açıldı, 3. ~6 dk sonra (Modal L4 sırası/plan sınırı) → bekleme 19,5 dk. `max_containers=10` yapıldı.
- Sonraki: `/video` uç noktası + sitede "Video / Sahne" sekmesi (sahne listesi, birleştirme, müzik); kısa animasyonları arka planı silinmiş sprite sheet'e çevirme.

## 1. ✅ Sipariş sistemi (siparis.yml) — 22-23 Kasım gece, kullanıcıyla canlı oturumda
- `siparis.yml` (girdi: hedef repo, dal, dosya, sadece, hizli, onceki): hedef repodaki `assets/siparis.json` → her satır paralel bir iş: motorla görsel (otomatik temizlik) → (`"hat": "komando"` ise) TripoSR 3D → `siparis/komando_hatti.py` (Blender: Komando'nun `asker.py` sahnesi + `asker2.py` Quaternius UAL iskeleti) → 8 yön × 8 animasyon sprite sayfası (Komando düzeni) + önizleme. Çıktılar `deneme-sonuclari/siparis/<repo>/<zaman>/`; AJAN_TOKEN varsa hedef repoya `assets/otomatik-<tarih>` dalı + PR (`siparis/teslim.py`).
- Motor "T-pose" tarifine rağmen kolları aşağıda çiziyor → hat kendisi çözüyor: mankenin kolları modele en iyi oturan açıya indirilir (KD-ağacı, 40–82°), ağırlık o pozdan aktarılır, model ters dönüşle T-poza açılır; kol-gövde ve bacak-bacak arası gerilen yüzler kesilir.
- `onceki` girdisi: önceki siparişin görselleriyle motor harcamadan yeniden render.
- İlk teslim: Komando Bölüm 9 karakterleri (alman_dag, alman_muhendis, isci, madenci, komando_nisanci). Süre: karakter başına ~25-35 dk (paralel), GPU ≈ 0,02 $/karakter.
- Sonraki: diğer oyunlar için 2D hat (yön seti + animasyon sekmesi çıktıları), AJAN_TOKEN gelince otomatik PR.

## 2. 🔄 Yapay zekâ ile gerçek animasyon (OpenPose ControlNet + IP-Adapter, /animate)
- 23 Kasım (gündüz, kullanıcıyla): `pozlar.py` (kodla OpenPose iskeletleri: bekleme, yürü, koş, saldır, ateş, zıpla, hasar), `anim_dene.yml`, canlı "animator" uygulaması (L4; T4'te bellek yetmedi; xinsir/controlnet-openpose-sdxl-1.0 Apache-2.0), "yan yana" yöntem (solda referans, sağda yeni kare), iş kuyruğu (`/is/animate`), sitede Animasyon → "Yapay zekâ ile", `anim_uret.yml`. Ateşte namlu alevi kodla.
- 24 Kasım (gece): **kare tutarlılığı** — (1) boy eşitleme (GPU'suz, `pozlar.boy_esitle`), (2) üçlü tuval (referans | önceki kare | yeni) varsayılan, sitede "Tutarlı silah/kıyafet" kutusu, (3) ayak dibi gölge temizliği (görsel motoru da). Karşılaştırma: `anim_dene` BCD (saldırı, seed 7) → `deneme-sonuclari/animasyon/20261123-2355/`. Süre: 8 kare yan yana 164 sn → üçlü 268 sn (L4 ≈ 0,06 $/animasyon).
- Sırada: silahlı karakterler için ayrı saldırı pozları (süngü hamlesi, dipçik), başlık/bere tutarlılığı (tarif başı), arkadan/önden yürüme (madde 4 ile birlikte), 12 karelik akıcı döngüler.
## 3. ⬜ Tileset (Wang/blob geçişleri, Godot .tres)
## 4. 🔄 Yön seti iyileştirme (arkadan görünüş, 4/8 yön) — Blender yolu (kullanıcı isteği, 22 Kasım akşam)
- `uc_boyut.yml` (GPU'suz, GitHub Actions, ~9 dk): görsel → **TripoSR** (MIT) ile 3D (.glb/.ply, CPU'da ~1 dk) → **Blender 4.2 LTS** (GPL; çıktılar serbest) ile 4/8 yönden şeffaf render → isteğe bağlı **motorla yeniden boyama** (render = şekil iskeleti, /edit güç 0.55; orijinal = IP-Adapter referansı 0.5).
- İlk sonuç (çizgi film kadın): ham 3D render bulanık (yüz silik) ama yönler tutarlı; **boyanmış hali çok iyi** — gerçek arkadan görünüş, kıyafet/saç/çizme her yönde aynı. Kusur: yan/arka görünüşte orijinalde olmayan bir sırt çantası eklendi (omuz kayışından). Maliyet: 4 yön boyama ≈ 130 sn GPU ≈ 0,02 $.
- TripoSR ekseni: model z-yukarı, ön yüz +x → Blender'da ön açı 270.
- Sırada: sitedeki "Yön seti"ne "3D ile (Blender)" seçeneği (motorda Blender/TripoSR uç noktası ya da Actions tetikleme), 8 yön, sprite sheet çıktısı; sonra .glb indirme (madde 5).
## 2b. 🔄 3D iskeletle animasyon (kullanıcı isteği, 22 Kasım akşam — "Komando askerleri gibi")
- `uc_boyut.yml` girdisi `anim=yuru,kos`: TripoSR modeli → `blender_anim.py` otomatik iskelet (boy/bacak/kol kesitlerden ölçülür, ağırlıklar kemiğe uzaklıkla, sol/sağ ayrımı) → kodla yürüme/koşma döngüsü → 8 yön × 8 kare, Commandos açısı (35°), 256 px, sprite sayfası + GIF. GPU'suz, ~6 dk.
- İlk sonuç (çizgi film kadın): yürüme ve koşma 8 yönde tutarlı, yandan adım net. Düzeltmeler: ön yön açısı; bacaklar/kollar arası gerilen yüzler kesildi (perde gitti). Kalan kusurlar: kollar yassı, bazı karelerde küçük delikler (içerisi görünüyor), yüz bulanık (TripoSR).
- Komando'nun kendi hattı (elle model + Quaternius CC0 animasyonlar) ayrı; bu, atölyede üretilen HER karakter için.
- Sırada: çömelme, sürünme, ateş, ölme; küçültme + pixel modu (64-128 px); karelerin motorla tutarlı boyanması (titremesiz) denemesi; sitedeki Animasyon sekmesine "3D ile" seçeneği.

## 5. 🔄 Görselden 3D model (.glb) — TripoSR denemesi `uc_boyut.yml` ile çalışıyor (model.glb çıktı); kalite düşük, iyileştirme adayı: TRELLIS (MIT)
## 6. ⬜ Ses efekti (.wav, "Ses" sekmesi)
## 7. ⬜ Sonrası: stil LoRA eğitimi, UI kit, kart çerçevesi nadirlik setleri

## Yedekler
- kararli-v3: 2026-11-20 (0a öncesi)
- kararli-v4: 2026-11-20 (DreamShaper'a geçiş öncesi)
- kararli-v5: 2026-11-21 (stil LoRA'ları öncesi)
- kararli-v6: 2026-11-22 (ders sistemi öncesi)
- kararli-v7: 2026-11-22 gece (hi-res fix + BiRefNet öncesi)
- kararli-v8: 2026-11-22 gece (tek silah + en iyisini seç öncesi)
- kararli-v9: 2026-11-23 gece (yüz düzeltme öncesi)
- kararli-v10: 2026-11-23 sabah (animator L4 öncesi — gündüz oturumu)
- kararli-v11: 2026-11-24 gece (animasyon tutarlılığı öncesi)

## Gece günlüğü
- 2026-11-20: 0a başladı — karşılaştırma iş akışı eklendi; DreamShaper deneme motoru açılmadı (3/3 deneme hakkı kullanıldı), canlı motor değişmedi.
- 2026-11-20 (gündüz, elle başlatıldı): sebep bulundu (zamanlayıcı), karşılaştırma tamamlandı, ana model DreamShaper XL'e geçti; canlı testler geçti. LoRA aday listesi çıkarıldı (0b hazırlığı).

- 2026-11-21 (gece): 0b — stil LoRA karşılaştırması (1 deneme motoru, 9 görsel), çizgi film + chibi LoRA'ları canlıya alındı, sitede "Stil güçlendirici".

- 2026-11-22 (gündüz, kullanıcıyla): Hamelinli Kavalcı denemeleri (4 üretim); uret.yml'ye referans girdisi; **ders sistemi** (DERSLER.md + motorda otomatik kurallar + pixel'de taslak→referans).

- 2026-11-22 (gece): 0c — hi-res fix (motor + site), BiRefNet-lite temizlik, yerel arka planla delik doldurma, temizlik_dene.yml.

- 2026-11-22 (gece, kullanıcı isteği): tek silah dersi (tutuş tarifi + CLIP taslak seçimi) + 0e en iyisini seç.

- 2026-11-24 (gece): madde 2 — animasyon kare tutarlılığı (boy eşitleme, üçlü tuval, ayak gölgesi); 1 deneme + 1 kurulum/test. Komando'ya yazma izni yine yok (oturuma bağlı değil).

- 2026-11-23 (gece): 0d — yüz düzeltme (motor + site + test), Komando için komando portreleri (Reilly, Blake) — bu oturumda Komando'ya yazma izni yoktu (add_repo yok, push 403) → `deneme-sonuclari/siparis/komando/portreler-20261123/`.

## Tahmini Modal harcaması (Kasım 2026)
- 19-20 Kasım: ~17 motor kurulumu + ~8 üretim + 3 karşılaştırma denemesi → tahmini 2-4 $ (20 $ sınırının çok altında).
- 20 Kasım akşamı (gündüz oturumu): ~4 kurulum+test daha → +~1 $
- 21 Kasım: 1 LoRA karşılaştırması + 1 kurulum/test → +~0.5 $. Ay toplamı tahmini 4-6 $.
- 21 Kasım sabah: Modal panelinde gerçek kullanım **3 $ / 30 $** (kullanıcının ekran görüntüsü). Video denemesi +~0,35 $.
- 22 Kasım: kavalcı üretimleri (4 iş) + 1 kurulum/test → +~0,5 $.
- 22 Kasım gece: 2 kurulum/test + 1 üretim → +~0,4 $. Kullanıcı isteğiyle +2 kurulum/test (tek silah) → +~0,4 $. Ay toplamı tahmini ~5-6 $ (20 $ sınırının altında).
- 23 Kasım gece: 2 kurulum/test (~17 dk'lık) + 2 portre üretimi (+2 başarısız) → +~0,45 $. Ay toplamı tahmini ~6-7 $ (20 $ sınırının altında).
- 24 Kasım gece: 1 animasyon denemesi (L4 ~16 dk) + 1 kurulum/duman testi → +~0,35 $. Ay toplamı tahmini ~7-8 $ (20 $ sınırının altında).
- 24 Kasım (gündüz, kullanıcıyla): Z-Image + Qwen denemeleri, 2 fil-kedi üretimi, Ressam kurulumu/testi, animatör hata ayıklama → +~1,2 $. Ay toplamı tahmini ~9-10 $ (20 $ sınırının altında).
