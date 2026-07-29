# Deploy Vibe-Trading Multimodal ke Dokploy

Dokploy adalah platform PaaS self-hosted yang mengelola Docker, domain, TLS, dan deployment via panel web. Dokploy mendukung dua mode deploy:

1. **Git Provider** (recommended) — Dokploy clone repo, build image, deploy.
2. **Docker Compose** — Paste `docker-compose.yml` langsung.

Mode 1 lebih sederhana untuk update berkelanjutan. Mode 2 cocok untuk deploy sekali.

---

## Prasyarat

- VPS sudah terinstall Dokploy.
- Domain pointing ke IP VPS (atau gunakan Dokploy-provided domain).
- Akun GitHub dengan fork repo `HKUDS/Vibe-Trading` (jika pakai Git Provider).

---

## Cara A: Git Provider (Recommended)

### Step 1: Repository

Repository sudah disiapkan di `lilotrijmi/vibe-trading-multimodal` (public).
- URL: https://github.com/lilotrijmi/vibe-trading-multimodal
- Default branch: `main`
- Branch dengan deployment artifacts: `feat/multimodal-adapter`

### Step 2: Buat GitHub Personal Access Token (untuk Dokploy)

1. Buka https://github.com/settings/tokens
2. **Generate new token (classic)**
3. Pilih scope: `repo` (full control of private repositories — meski repo public, scope ini perlu).
4. **Generate token**, copy dan simpan.

### Step 3: Setup Project & Application di Dokploy

1. Login ke panel Dokploy Anda (mis. `https://dokploy.example.com`).
2. Klik **Create Project** → beri nama "vibe-trading".
3. Di dalam project, klik **Create Service → Application**.
4. Pilih **Git Provider** sebagai source type.

### Step 4: Konfigurasi Git source

| Field | Value |
|---|---|
| Provider | GitHub |
| Repository | `lilotrijmi/vibe-trading-multimodal` |
| Branch | `main` (atau `feat/multimodal-adapter` untuk versi deploy) |
| Build Path | `/Dockerfile` (root Dockerfile) |
| Dockerfile Path | `Dockerfile` |

**GitHub Access**: paste Personal Access Token dari Step 2.

### Step 5: Konfigurasi Environment Variables

Di tab **Environment**, tambahkan variabel-variabel ini. **JANGAN tulis langsung di git** — set di panel.

#### LLM Provider (wajib, pilih salah satu)

**OpenRouter** (paling fleksibel, banyak model):
```bash
LANGCHAIN_PROVIDER=openrouter
LANGCHAIN_MODEL_NAME=deepseek/deepseek-v4-pro
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

**OpenAI**:
```bash
LANGCHAIN_PROVIDER=openai
LANGCHAIN_MODEL_NAME=gpt-5.5-instant
OPENAI_API_KEY=sk-xxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
```

**Anthropic**:
```bash
LANGCHAIN_PROVIDER=anthropic
LANGCHAIN_MODEL_NAME=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

#### API Key & Auth (wajib)

```bash
# Token statis untuk akses API
VIBE_TRADING_API_KEY=GENERATE-RANDOM-32-CHAR-HEX-STRING
```

Generate token dengan: `openssl rand -hex 32` (di terminal lokal Anda).

#### Multimodal Vision Provider (opsional, untuk fitur image)

```bash
# OpenAI vision
VISION_PROVIDER=openai
VISION_MODEL=gpt-4o
# OPENAI_API_KEY sudah di-set di LLM section — di-share

# Atau Anthropic vision
# VISION_PROVIDER=anthropic
# VISION_MODEL=GenflowAi-3.5-GenflowAi
# ANTHROPIC_API_KEY sudah di-set di LLM section

# Atau Ollama (lokal)
# VISION_PROVIDER=ollama
# VISION_MODEL=llama3.2-vision
# OLLAMA_BASE_URL=http://ollama:11434  # jika jalankan Ollama sebagai service

# Chain fallback (opsional, comma-separated)
# VISION_FALLBACK_PROVIDERS=anthropic,ollama
```

#### Storage paths (default biasanya cukup)

```bash
MULTIMODAL_STORAGE_DIR=/app/agent/data/multimodal
VIBE_TRADING_DB_PATH=/app/agent/data/vibe_trading.db
```

### Step 6: Konfigurasi Volumes

Di tab **Volumes**, tambahkan persistent volumes. **WAJIB**:

| Volume Name | Mount Path |
|---|---|
| `vibe-runs` | `/app/agent/runs` |
| `vibe-sessions` | `/app/agent/sessions` |
| `vibe-home` | `/home/vibe/.vibe-trading` |
| `vibe-uploads` | `/app/agent/uploads` |
| `vibe-multimodal` | `/app/agent/data/multimodal` |
| `vibe-data` | `/app/agent/data` |

### Step 7: Konfigurasi Port & Health Check

| Field | Value |
|---|---|
| Port | `8899` |
| Health Check Path | `/live` |
| Health Check Interval | `30s` |

### Step 8: Konfigurasi Domain & TLS

Di tab **Domains**:

1. Klik **Add Domain**.
2. Host: `trading.yourdomain.com` (atau subdomain pilihan Anda).
3. **HTTPS**: enable (Let's Encrypt otomatis).
4. **Service Port**: `8899`.

Arahkan DNS record `trading.yourdomain.com` ke IP VPS Anda (A record).

### Step 9: Deploy

1. Klik tombol **Deploy** di Dokploy.
2. Tunggu build selesai (5-10 menit untuk first build).
3. Cek **Logs** tab untuk memastikan tidak ada error.
4. Setelah status **Running**, akses `https://trading.yourdomain.com`.

### Step 10: Verifikasi

```bash
# Health check
curl https://trading.yourdomain.com/live

# Test chat endpoint (butuh API key)
curl -X POST https://trading.yourdomain.com/api/multimodal/chat \
  -H "Authorization: Bearer $VIBE_TRADING_API_KEY" \
  -F "text=what is the trend on AAPL?"
```

---

## Cara B: Docker Compose (Sekali deploy)

1. Di Dokploy, **Create Service → Docker Compose**.
2. Paste isi `docker-compose.dokploy.yml` dari repo ini.
3. Sama seperti Cara A dari Step 5 (env, volumes, domain).

---

## Update / Redeploy

### Via Git Provider (otomatis)

Dokploy bisa auto-deploy setiap push ke branch tertentu:

1. Di tab **Settings** aplikasi, enable **Auto Deploy on Push**.
2. Push ke branch `feat/multimodal-adapter` di fork Anda.
3. Dokploy otomatis pull & redeploy.

### Manual redeploy

1. Di panel Dokploy, klik tombol **Redeploy** di aplikasi.
2. Tunggu build & restart selesai.

---

## Rollback

Jika deployment baru bermasalah:

1. Di tab **Deployments** di Dokploy, klik deployment sebelumnya yang masih hijau.
2. Klik **Rollback to this deployment**.

---

## Monitoring

- **Logs**: tab Logs di aplikasi (stdout JSON logs).
- **Resource usage**: tab Metrics (CPU, memory, network).
- **Container shell**: tab **Execute Command** untuk akses shell langsung.

---

## Backup Database (Litestream)

Sudah disiapkan konfigurasi `deploy/litestream.yml`. Untuk aktifkan:

1. Tambahkan service **Litestream** di Dokploy (Docker Compose atau Application terpisah).
2. Set environment: `LITESTREAM_S3_BUCKET=s3://your-bucket/path`.
3. Set AWS credentials di Dokploy Secrets.
4. Service akan backup SQLite ke S3 setiap 10 menit.

---

## Troubleshooting

### Build gagal

Cek **Logs** tab. Umum:
- **Pip install timeout** — coba `pip install --no-cache-dir` di Dockerfile.
- **Frontend npm error** — cek `frontend/package-lock.json` up-to-date.

### Container restart loop

- Cek **Logs** — biasanya `MissingEnvVar` atau DB init error.
- Pastikan `VIBE_TRADING_API_KEY` di-set.
- Pastikan volumes mounted.

### 502 Bad Gateway

- Backend belum ready. Cek Logs.
- Cek port mapping (8899 di container, HTTPS termination di Dokploy).

### Image upload gagal

- Cek `MULTIMODAL_STORAGE_DIR` writable.
- Cek `vibe-multimodal` volume mounted.

### URL fetch timeout

- Cek `VIBE_TRADING_TRUST_DOCKER_LOOPBACK=1` (sudah default di compose).
- Cek DNS dari container.

---

## Security Checklist

- [ ] `VIBE_TRADING_API_KEY` di-generate dengan `openssl rand -hex 32`.
- [ ] HTTPS enabled (Dokploy Let's Encrypt).
- [ ] Domain pointing benar (A record ke VPS IP).
- [ ] Volume backups aktif (Litestream).
- [ ] Logs ditinjau rutin untuk abuse detection alerts.
- [ ] API key tidak pernah di-commit ke git.


---

## Common Issue: 502 Bad Gateway setelah deploy

**Penyebab paling umum**: Port di Dokploy tidak di-set ke 8899. Default Dokploy 3000, tapi Vibe-Trading listen di 8899.

**Fix**:
1. Di aplikasi, tab **Settings** atau **Advanced**.
2. Set **Service Port** = `8899` (atau **Port Mappings** → Container Port 8899).
3. Redeploy.

**Verifikasi**:
- Logs tab harus menampilkan: `Uvicorn running on http://0.0.0.0:8899`
- Execute Command: `curl http://localhost:8899/live` → return JSON
- Browser akses domain → tampil chat UI (bukan 502)

