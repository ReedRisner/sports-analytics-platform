# Deployment Guide (Frontend + Backend + Domain)

This project is currently configured for local development (`localhost`).

## Recommended architecture

- **Frontend (React/Vite):** Deploy to Vercel (or Netlify/Cloudflare Pages).
- **Backend (FastAPI):** Deploy to Render, Railway, Fly.io, or an EC2/Docker host.
- **Database (PostgreSQL):** Use managed Postgres (Neon, Supabase, Railway, Render Postgres, RDS).
- **Domain + DNS:** Buy domain in Namecheap/Cloudflare and point subdomains:
  - `app.yourdomain.com` → frontend host
  - `api.yourdomain.com` → backend host

## 1) Backend deployment checklist

1. Provision PostgreSQL and copy connection string.
2. Set backend environment variables:
   - `DATABASE_URL`
   - `SECRET_KEY`
   - `ACCESS_TOKEN_EXPIRE_MINUTES`
   - `ODDS_API_KEY`
3. Build/start command example:
   - Install: `pip install -r requirements.txt`
   - Run: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. Run Alembic migrations in deploy pipeline:
   - `alembic upgrade head`
5. Expose `/health` endpoint for platform health checks.

## 2) Backend code updates you should make

### A) CORS should include production frontend domain

Replace localhost-only CORS with env-driven origins:

```python
# in backend/app/main.py
import os

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, set:

```bash
ALLOWED_ORIGINS=https://app.yourdomain.com
```

### B) Ensure startup creates/migrates schema only once

Currently the app creates tables on startup and also has Alembic. In production, prefer Alembic only.

- Keep `alembic upgrade head` in deployment.
- Optionally remove `Base.metadata.create_all(bind=engine)` from app startup once migrations are reliable.

## 3) Frontend deployment checklist

1. Build command:
   - `npm ci`
   - `npm run build`
2. Output directory: `dist`
3. Set environment variable:
   - `VITE_API_URL=https://api.yourdomain.com`
4. Deploy `dist` on Vercel/Netlify.

## 4) Frontend code updates you should make

Your API client already reads `VITE_API_URL`, so production mostly needs env setup.

`.env.production` example (frontend):

```bash
VITE_API_URL=https://api.yourdomain.com
```

## 5) Domain and SSL

1. Buy domain (or use existing).
2. In DNS:
   - `CNAME app` → frontend platform target.
   - `CNAME api` → backend platform target.
3. Enable HTTPS certificates on hosting providers (usually automatic).
4. Verify:
   - `https://app.yourdomain.com`
   - `https://api.yourdomain.com/health`

## 6) Suggested first production setup (fastest path)

- Frontend: **Vercel**
- Backend: **Render Web Service**
- DB: **Neon Postgres**

This gives easy env vars, HTTPS, logs, and custom domain support.

## 7) Production hardening

- Add rate limiting and request logging.
- Rotate `SECRET_KEY` and store secrets only in platform env vars.
- Add monitoring (Sentry/Datadog) and uptime checks on `/health`.
- Restrict CORS to your exact frontend domain(s).
- Set backup policy for PostgreSQL.
