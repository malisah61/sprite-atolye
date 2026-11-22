# Dersler — tekrar eden hatalardan öğrenilenler

Motor bu kuralları her üretimde otomatik uygular (`modal/app.py` → `DERSLER`). Sitede sonuç kartında "dersler: ..." diye görünür.
**Kural:** Bir hata ikinci kez görülürse buraya yazılır ve `DERSLER` listesine bir satır eklenir. Her gece önce bu dosya okunur.

| Tarih | Görülen hata | Ders (uygulanan çözüm) |
|---|---|---|
| 22 Kasım | Pixel'de keman sopaya/direğe, kitap çantaya, kaval değneğe dönüştü | Pixel + elde nesne → **önce detaylı taslak, sonra taslak referans (0.4) ile pixel** (`iki_asama`). Nesneye göre negatif: kaval → "violin, walking stick, cane, staff, branch..."; keman → "cane, pole, briefcase"; kitap → "briefcase, bag" |
| 22 Kasım | İnsan karakterlere elf kulağı çıktı | İnsan anahtar kelimeleri (man, woman, piper, knight...) → negatif "elf ears, pointed ears" (elf/goblin/şeytan tarifinde uygulanmaz) |
| 22 Kasım | Aynı nesneden iki tane (iki kaval, başın arkasında fazladan çubuk) | Negatif "second flute, extra flute / second sword, extra weapon, floating weapon" |
| 22 Kasım | Ders testinde kaval tamamen kayboldu (negatife "staff, branch, spear" yazılmıştı) | Negatifi hafif tut; taslaktan 2 aday çiz, CLIP ile "kavalı ağzında" olanı seç (`kontrol`) |
| 22 Kasım | Referans gücü 0.6'da pixel yarı-ressamca kaldı | Pixel'e çevirirken referans gücü **0.4** (karakter korunuyor, pixel keskin) |

## Açık sorunlar (henüz kural yok)
- Küçük yan figürler (kavalcının faresi) çoğu zaman çizilmiyor.
- Beyaz gömlek/yaka arka plan sanılıp silinebiliyor (beyaz hale, delik) — temizlik tarafında bakılacak.
- Çizgi film stilinde ara ara karakter sayfası (aynı kişi 3 açıdan).
