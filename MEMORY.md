# Kararsızım — Proje Durumu ve Hafıza (MEMORY.md)

Bu dosya, projenin mevcut durumunu, tamamlanan fazları, mimari kararları ve deployment (canlıya çıkış) için yapılacak adımları içerir.

---

## 1. Tamamlanan Fazlar ve Mevcut Durum

### ✅ Faz 0 — İskelet ve Yerel Çalışma (`db0db3f`)
- Python 3.14 + Django 6.1.2 ve ilgili kütüphaneler (`requirements.txt`) kuruldu.
- Sanal ortam (`.venv`), `.gitignore`, `.env.example` hazırlandı.
- `config`, `accounts`, `polls` Django uygulamaları oluşturuldu.
- `settings.py` üzerinde SQLite fallback, Türkçe dil desteği (`tr`), `Europe/Istanbul` saat dilimi, `WhiteNoise` ayarlandı.

### ✅ Faz 1 — Veri Modeli ve Supabase Bağlantısı (`ee70364`)
- `accounts.User` (özel kullanıcı modeli; küçük harf email, regex kontrollü kullanıcı adı) tanımlandı ve `AUTH_USER_MODEL` ilk migration öncesi bağlandı.
- `polls.Poll`, `polls.Option`, `polls.Vote` modelleri tanımlandı.
- `public_id` (10 karakterlik Base62) üreteci yazıldı.
- Supabase PostgreSQL bağlantısı (Session pooler: 5432, Transaction pooler: 6543) üzerinden tablolar oluşturuldu ve `seed_demo` komutuyla demo veriler başarıyla aktarıldı.
- Aynı kullanıcının veya anonim session'ın mükerrer oy kullanmasını engelleyen veritabanı kısıtları (`UniqueConstraint`) doğrulandı.

### ✅ Faz 2 — Kimlik Doğrulama (`3c3c890`)
- Kayıt, giriş ve çıkış formları/view'ları yazıldı (`RegisterForm`, `SiteLoginView`, `LogoutView`).
- Giriş yapmamış kullanıcı `/anket/olustur/` sayfasına gittiğinde `?next=` ile yönlendirildi ve özel bilgilendirme mesajı gösterildi.
- E-posta adresinin arayüzde veya HTML çıktısında hiçbir yerde sızdırılmadığı doğrulandı.

### ✅ Faz 3 — Anket Oluşturma ve Akış (`93320a3`)
- `PollForm` ve dinamik seçenek ekleme/kaldırma JavaScript'i (`poll-form.js`) yazıldı (en az 2, en fazla 5 seçenek; JS kapalıyken de sunucu tarafı 2–5 doğrulaması çalışır).
- Ana sayfa kart ızgarası, sekmeler (**Yeni**, **Popüler** - son 7 günün oyları, **Kapananlar**) ve kümülatif sayfalama eklendi.
- N+1 sorgu problemi önlendi (`select_related("author")` + `prefetch_related("options")`).
- Anket detay ve profil sayfaları oluşturuldu.

### ✅ Faz 4 — Oylama ve Sonuçlar (`0d57fc1`)
- Oylama motoru (`cast_vote` servisi, atomik `F()` ifadeleriyle sayaç artırımı) uygulandı.
- **Sürü psikolojisini kırma:** Oy verilmeden önce seçenek yüzdeleri gizlendi; oy verildikten sonra veya anket kapatıldıktan sonra açıldı.
- `vote.js` ile asenkron `fetch` (CSRF destekli) oy verme ve animasyonlu doldurma, JS kapalıyken standart form POST fallback'i sağlandı.
- Yüzde yuvarlama motoru (toplamın her zaman %100 olması için kalan farkın en çok oyu alan seçeneğe eklenmesi) uygulandı.
- Anket sahibine özel anketi kapatma ve onaylı silme özellikleri eklendi.

### ✅ Faz 5 — Arayüz Cilası (`07c26af`)
- `tokens.css`, `base.css` ve `components.css` tasarım sistemi şartnameye göre tamamlandı (ham hex kodu kullanılmadı, sadece CSS değişkenleri kullanıldı).
- Google Fonts (`Bricolage Grotesque`, `Inter`, `JetBrains Mono` latin-ext alt kümesiyle) bağlandı.
- `logo.svg`, `og-default.svg`, favicon ve dinamik Open Graph meta etiketleri eklendi.
- Klavye odağı (`--sun` halkası), mobil 360px uyumluluğu, `aria-live="polite"` ve `prefers-reduced-motion` destekleri sağlandı.
- Özel `404.html` ve `500.html` şablonları eklendi.
- `DEBUG=False` ve `collectstatic` (WhiteNoise) ortamında tüm sayfaların ve 404 ekranının çalıştığı test edildi.

---

## 2. Test Durumu
- Django test suite'i (`python manage.py test`) altında toplam **59 test** bulunmaktadır.
- Tüm testler eksiksiz ve yeşil (**OK**) durumdadır.

---

### ✅ Faz 6 — Vercel'e Deployment Hazırlığı
- `config/settings.py` içerisine production güvenlik ayarları (`SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`) eklendi. Test runner sırasında SSL yönlendirmesinin testleri kırmaması sağlandı.
- Modern Vercel standardına uygun `vercel.json` oluşturuldu (`config/wsgi.py` fonksiyonu, `maxDuration: 30`).
- Kapsamlı `docs/DEPLOY.md` rehberi oluşturuldu (Supabase Transaction vs Session Pooler farkı, yerel migration komutları, ortam değişkenleri ve deployment adımları).
- Test paketi (59 test) eksiksiz doğrulandı.

---

## 2. Test Durumu
- Django test suite'i (`python manage.py test`) altında toplam **59 test** bulunmaktadır.
- Tüm testler eksiksiz ve yeşil (**OK**) durumdadır.

---

## 3. Canlıya Çıkış Adımları (Deploy Aşamasında)

1. **Git Değişikliklerinin Gönderilmesi:**
   - Değişikliklerin `origin/main` branch'ine pushlanması.
2. **Vercel Entegrasyonu & Environment Variables:**
   - Vercel Dashboard üzerinden projeyi import etmek veya `npx vercel` komutunu çalıştırmak.
   - Gerekli 6 adet ortam değişkeninin (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `VOTER_KEY_SALT`, `DATABASE_URL`) Vercel'e girilmesi.
3. **Canlı Doğrulama (Smoke Test):**
   - Canlı URL üzerinden kayıt olma, anket oluşturma, oy kullanma ve 404 testleri.

---

## 4. İsteğe Bağlı Sonraki Adım: Faz 7 — Sertleştirme
- Anonim oylar için IP hash tabanlı saatlik hız sınırı (rate limit).
- Kayıt formunda honeypot alanı (spam bot koruması).
- Anket paylaş butonu (`navigator.share` / panoya kopyalama).
- Soru arama (`icontains`).

