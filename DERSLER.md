# Dersler — tekrar eden hatalardan öğrenilenler

Motor bu kuralları her üretimde otomatik uygular (`modal/app.py` → `DERSLER`; temizlik dersleri doğrudan temizlik kodunda).
Temizlik hatası şüphesinde: ham görseli `uret.yml` (temizle=false) ile üret, sonra `temizlik_dene.yml` ile adım adım bak (GPU harcamaz). Sitede sonuç kartında "dersler: ..." diye görünür.
**Kural:** Bir hata ikinci kez görülürse buraya yazılır ve `DERSLER` listesine bir satır eklenir. Her gece önce bu dosya okunur.

| Tarih | Görülen hata | Ders (uygulanan çözüm) |
|---|---|---|
| 22 Kasım | Pixel'de keman sopaya/direğe, kitap çantaya, kaval değneğe dönüştü | Pixel + elde nesne → **önce detaylı taslak, sonra taslak referans (0.4) ile pixel** (`iki_asama`). Nesneye göre negatif: kaval → "violin, walking stick, cane, staff, branch..."; keman → "cane, pole, briefcase"; kitap → "briefcase, bag" |
| 22 Kasım | İnsan karakterlere elf kulağı çıktı | İnsan anahtar kelimeleri (man, woman, piper, knight...) → negatif "elf ears, pointed ears" (elf/goblin/şeytan tarifinde uygulanmaz) |
| 22 Kasım | Aynı nesneden iki tane (iki kaval, başın arkasında fazladan çubuk) | Negatif "second flute, extra flute / second sword, extra weapon, floating weapon" |
| 22 Kasım | Ders testinde kaval tamamen kayboldu (negatife "staff, branch, spear" yazılmıştı) | Negatifi hafif tut; taslaktan 2 aday çiz, CLIP ile "kavalı ağzında" olanı seç (`kontrol`) |
| 22 Kasım | Referans gücü 0.6'da pixel yarı-ressamca kaldı | Pixel'e çevirirken referans gücü **0.4** (karakter korunuyor, pixel keskin) |
| 22 Kasım (gece) | Temizlik figürün parçasını arka plan sandı: aslan adamın **gri baltası ve onu tutan eli** silindi (beyaz gömlek sorunuyla aynı aile — 2. kez) | Arka plan silme modeli **isnet → BiRefNet-lite** (MIT). GPU'suz `temizlik_dene.yml` ile aynı görselde balta + el eksiksiz çıktı. Eskiye dönüş: `app.py` → `REMBG_MODEL` |
| 22 Kasım (gece) | Arka plan vinyetli (ortası açık gri) olunca kol-gövde arasındaki gerçek boşluklar **gri yama** olarak geri geldi | `fill_holes` artık tek renk yerine **yerel arka plan tahmini** ile kıyaslıyor |

| 22 Kasım (gece) | Sadece "battle axe" istenen aslan adama model fazladan bir **kılıç** ekledi (bacağın içinden geçiyor). Kullanıcı uyardı: "kılıç olmaz başka bir şey olur" — yasaklamak yerine çözüm | **Tek silah** dersi (yasak yok): (1) tarife elin ne yaptığı yazılır ("wielding a single battle axe with both hands"; kalkan varsa "kalkan diğer elde"); (2) 4 hızlı taslakta CLIPSeg ile "weapon" bölgeleri sayılır, tek silahlı taslak seçilir (ilk denemede CLIP'in tüm resme bakarak puanlaması kılıcı ayırt edemedi — `silah_dene.yml` ile ölçüldü: kılıçlı görsellerde 3 bölge, sadece baltalıda 1); (3) birden çok adayda tarife en uyumlu olan başa konur (⭐ en iyi). Sadece karakter tariflerinde, tek bir silah adı geçiyorsa ("dual/two/both" yoksa) |
| 23 Kasım (gece) | Sipariş/Komando hattı: tarifte "T-pose, arms stretched out" yazmasına rağmen 3 adayın üçü de kollar aşağıda çizildi (2 sipariş üst üste) | Tarifle zorlamak yerine **3D tarafında çöz**: mankenin kolları modele oturan açıya indirilir, ağırlık o pozdan aktarılır, model ters dönüşle T-poza açılır (`siparis/komando_hatti.py`). Aday seçimi: gerçek T-poz (en/boy > 0.8) varsa o, yoksa motorun en iyisi |
| 23 Kasım (gece) | Kare (1024×1024) görselde ekstra kalite 1536×1536'ya çıkınca motor çıplak "500" verdi (2 portre isteği üst üste) | Hi-res'te toplam piksel de sınırlı (≤1,65 MP → kare 1024 → 1280); bellek yetmezse görsel ilk haliyle döner; motor hatası artık ayrıntılı (tür + iz) döner, `uret.yml` yazdırır |
| 23 Kasım (gece) | Çizgi film kadında iki göz farklı renk/biçim (tam boy görselde yüz küçük kalıyor) — ilk kez not edildi | Kural değil özellik: **yüz düzeltme** (`"yuz": true`, sitede varsayılan açık). Test görselinde gözler eşitlendi. Tekrar görülürse yüz düzeltmenin gücü (0.4) ya da kırpıntı oranı (2.2x) ayarlanacak |
| 23 Kasım (sabah) | Sitede "Hata: Failed to fetch": ekstra kalite + yüz düzeltme + temizlik açıkken üretim 150 sn'yi aşıyor; Modal web uç noktası 150 sn'den uzun isteğe CORS başlıksız 303 yönlendirme dönüyor (`motor_dene.yml` ile ölçüldü: 303, 150 sn) | Uzun işler **iş kuyruğuyla**: `POST /is/generate|edit` hemen `{is}` döner, site `GET /is/<id>` yoklar; motor `@modal.concurrent` (yoklamalar beklemesin) + `gpu_kilit`. Aynı ayarlarla canlı test: iş 263 sn'de bitti (soğuk başlangıç dahil). Yeni uzun uç nokta eklerken 150 sn sınırını unutma |

## Açık sorunlar (henüz kural yok)
- Küçük yan figürler (kavalcının faresi) çoğu zaman çizilmiyor.
- Beyaz gömlek/yaka arka plan sanılıp silinebiliyor — BiRefNet'e geçişle düzelmesi bekleniyor, gözlenecek.
- Temizlik testlerinde zombinin ayak dibinde küçük gri gölge kalıntısı.
- Portrelerde başlık/rozet tutmuyor (23 Kasım: "green beret" istenen Reilly'de bir aday başı açık, diğeri kasketli; şapka rozetleri uydurma). Tekrar görülürse: başlığı tarifin başına al / CLIP kontrolüyle ('wearing a beret' vs 'peaked cap') taslak seç.
- Çizgi film stilinde ara ara karakter sayfası (aynı kişi 3 açıdan).
