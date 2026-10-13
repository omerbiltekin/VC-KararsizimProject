# Kararsızım — Vercel Deployment Rehberi (DEPLOY.md)

Bu rehber, **Kararsızım** projesinin Vercel ve Supabase üzerinde canlıya (production) alınması adımlarını içerir.

---

## 1. Mimari ve Önemli Prensipler

- **Sıfır Konfigürasyon:** Vercel, modern Django desteği ile `manage.py`, `WSGI_APPLICATION = "config.wsgi.application"` ve `STATIC_ROOT` ayarlarını otomatik algılar. Eski `api/index.py` sarmalayıcıları veya karmaşık routing tanımları kullanılmaz.
- **Statik Dosyalar:** Vercel build sırasında `collectstatic` komutunu otomatik çalıştırır ve statik dosyaları doğrudan global CDN üzerinden servis eder.
- **Veritabanı (Supabase):**
  - **Uygulama Çalışırken (Runtime):** Supabase **Transaction Pooler (Port 6543)** kullanılır (`DATABASE_URL`). Serverless mimaride bağlantı tüketimini engeller (`conn_max_age=0`, `DISABLE_SERVER_SIDE_CURSORS=True`, `prepare_threshold=None`).
  - **Migration Çalıştırırken:** Supabase **Session Pooler (Port 5432)** kullanılır (`DATABASE_URL_DIRECT`). Transaction pooler DDL/migration işlemlerini desteklemez.
  - **Asla doğrudan IPv6 adresi (`db.<ref>.supabase.co:5432`) kullanılmamalıdır**, daima pooler adresi (`aws-0-<bölge>.pooler.supabase.com`) tercih edilmelidir.

---

## 2. Veritabanı Migration'larını Yerelden Çalıştırma

> [!IMPORTANT]
> Migration'lar Vercel build sırasında **çalıştırılmaz**. Canlıya çıkmadan önce veya model değişikliklerinde yerel terminalden Session Pooler (port 5432) kullanılarak veritabanına uygulanmalıdır.

Yerelde `.env` dosyanızda `DATABASE_URL_DIRECT` tanımlıysa:

```bash
# Session Pooler üzerinden canlı veritabanına migration uygulamak için:
DATABASE_URL="$DATABASE_URL_DIRECT" python manage.py migrate
```

Eğer ilk defa deploy ediyorsanız ve demo verileri yüklemek isterseniz:
```bash
DATABASE_URL="$DATABASE_URL_DIRECT" python manage.py seed_demo
```

Superuser (Admin) hesabı oluşturmak için:
```bash
DATABASE_URL="$DATABASE_URL_DIRECT" python manage.py createsuperuser
```

---

## 3. Vercel Ortam Değişkenleri (Environment Variables)

Vercel Dashboard'da projenin **Settings > Environment Variables** bölümüne (veya `vercel env add` ile) aşağıdaki değişkenler eklenmelidir:

| Değişken Adı | Örnek / Açıklama Değeri | Açıklama |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(50+ karakterli rastgele anahtar)* | `python -c "import secrets; print(secrets.token_urlsafe(50))"` ile üretin |
| `DJANGO_DEBUG` | `False` | Canlıda mutlaka False olmalı |
| `DJANGO_ALLOWED_HOSTS` | `.vercel.app` (veya varsa özel domain `ornek.com`) | İzin verilen hostlar (virgülle ayrılmış) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://*.vercel.app` (veya `https://kararsizim.vercel.app`) | CSRF doğrulamasını geçecek origin'ler |
| `VOTER_KEY_SALT` | *(32+ karakterli rastgele tuz)* | `python -c "import secrets; print(secrets.token_hex(16))"` ile üretin |
| `DATABASE_URL` | `postgresql://postgres.<REF>:<PAROLA>@aws-0-<BOLGE>.pooler.supabase.com:6543/postgres` | **Transaction Pooler (Port 6543)** |

> [!TIP]
> Güçlü secret key ve salt üretmek için terminalinizde şu komutu çalıştırabilirsiniz:
> ```bash
> python3 -c "import secrets; print('DJANGO_SECRET_KEY=' + secrets.token_urlsafe(50)); print('VOTER_KEY_SALT=' + secrets.token_hex(16))"
> ```

---

## 4. Vercel'e Deploy Etme Yöntemleri

### Yöntem A: GitHub Entegrasyonu (Önerilen)

1. Değişiklikleri GitHub'a gönderin (`git push origin main`).
2. [Vercel Dashboard](https://vercel.com/dashboard)'a gidin.
3. **Add New... -> Project** seçeneğine tıklayın.
4. `VC-KararsizimProject` GitHub reposunu seçin ve **Import** deyin.
5. **Environment Variables** bölümüne yukarıdaki Tablo 3'teki değişkenleri ekleyin.
6. **Deploy** butonuna tıklayın.

### Yöntem B: Vercel CLI / npx

Terminal üzerinden komut satırıyla deploy etmek için:

```bash
# İlk defa projeyi bağlamak ve deploy etmek için:
npx vercel

# Production deploy'u için:
npx vercel --prod
```

---

## 5. Canlı Doğrulama (Smoke Test) Kontrol Listesi

Deploy tamamlandıktan sonra verilen Vercel URL'i üzerinde şu kontrolleri yapın:

- [ ] Ana sayfa açılıyor, CSS ve görseller düzgün yükleniyor (statik dosya 404 hatası yok).
- [ ] Yeni bir kullanıcı kaydı (`/kayit/`) oluşturulabiliyor.
- [ ] Giriş yapılıp yeni bir anket açılabiliyor (`/anket/olustur/`).
- [ ] Oluşturulan ankete oy verilebiliyor ve oy sonrası sonuçlar animasyonla görüntüleniyor.
- [ ] Sayfa yenilendiğinde oy durumu korunuyor ve mükerrer oy engelleniyor.
- [ ] Var olmayan bir URL'e gidildiğinde (`/test-404-sayfasi/`) özel `404.html` sayfası görüntüleniyor.
- [ ] Açılış hızı ve ilk soğuk başlatma (cold start) sonrasında hata alınmadığı teyit ediliyor.
