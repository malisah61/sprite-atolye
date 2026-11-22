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

| 22 Kasım (gece) | Sadece "battle axe" istenen aslan adama model fazladan bir **kılıç** ekledi (bacağın içinden geçiyor). Kullanıcı uyardı: "kılıç olmaz başka bir şey olur" — yasaklamak yerine çözüm | **Tek silah** dersi (yasak yok): (1) tarife elin ne yaptığı yazılır ("wielding a single battle axe with both hands"; kalkan varsa "kalkan diğer elde"); (2) 4 hızlı taslak CLIP ile "tek silah" / "fazladan silah" diye puanlanıp temiz olan seçilir; (3) birden çok adayda tarife en uyumlu olan başa konur (⭐ en iyi). Sadece karakter tariflerinde, tek bir silah adı geçiyorsa ("dual/two/both" yoksa) |

## Açık sorunlar (henüz kural yok)
- Küçük yan figürler (kavalcının faresi) çoğu zaman çizilmiyor.
- Beyaz gömlek/yaka arka plan sanılıp silinebiliyor — BiRefNet'e geçişle düzelmesi bekleniyor, gözlenecek.
- Temizlik testlerinde zombinin ayak dibinde küçük gri gölge kalıntısı.
- Çizgi film stilinde ara ara karakter sayfası (aynı kişi 3 açıdan).
