# nud

A distributed streaming service with JIT (just-in-time) video processing.

Content metadata is sourced from TMDB and matched against live stream sources at request time. Only confirmed-available titles are surfaced to users.

---

## Engineering Highlights

**Availability State Machine**
Content goes through an explicit state machine before it's shown to users. Rather than a nullable `source_slug` column, availability is tracked as a first-class concern with its own model, status transitions, exponential backoff retry, and consecutive-failure tolerance to avoid flipping healthy content on transient scraper blips.

**JIT Stream Resolution**
Streams are resolved at play-time using a headless browser pipeline. The resolver intercepts network traffic to extract raw HLS manifests and subtitle tracks without relying on APIs that don't exist.

**Swappable Execution Driver**
The availability checking system is decoupled from its execution strategy. On free tier it runs inline on startup. On paid tier a single env var (`AVAILABILITY_DRIVER=arq`) switches it to a proper task queue with Redis broker and scheduled cron sweeps — zero code changes required.

**Redis Session Management**
Browser session cookies are stored in Redis with a 7-day TTL instead of local files. Cookies survive deploys, are shared across instances when scaled, and never end up in version control.

**Async-First Architecture**
Fully async Python stack — FastAPI, SQLAlchemy async, aiohttp. Playwright runs in isolated thread pool workers so the uvicorn event loop is never blocked during stream resolution.

---

## Stack

**Backend**
- Python 3.11+ / FastAPI
- PostgreSQL + SQLAlchemy (async)
- Redis — caching + session state
- Playwright — JIT stream resolution
- TMDB API — content metadata

**Frontend**
- React 19 + Vite
- Tailwind CSS
- hls.js — HLS stream playback
- Zustand — state management
- Axios

---

## Project Structure

```
nud/
├── backend/
│   ├── auth/           # Google OAuth + JWT
│   ├── availability/   # Content availability state machine
│   ├── enrichment/     # TMDB integration
│   ├── models/         # SQLAlchemy models
│   ├── proxy/          # HLS proxy
│   ├── routers/        # API endpoints
│   ├── scrapers/       # JIT stream resolvers
│   ├── schemas/        # Pydantic schemas
│   └── workers/        # DB writer
└── frontend/
    └── src/
        ├── api/        # Axios client
        ├── components/ # UI components
        ├── pages/      # Route pages
        └── store/      # Zustand stores
```

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Copy the example env file and fill in your values:
```bash
cp .env.example .env
```

Required env vars:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/nud
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-here
TMDB_API_KEY=your-tmdb-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
FRONTEND_URL=http://localhost:5173
APP_ENV=development
CORS_ORIGINS=["http://localhost:5173"]
BACKEND_URL=
```

Start the backend:
```bash
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
```

Required env vars:
```
VITE_API_URL=http://localhost:8000
```

Start the frontend:
```bash
npm run dev
```

---

## How It Works

### Availability System

Content goes through a state machine before it's shown to users:

```
PENDING → CHECKING → MATCHED   ← shown on home/search
                   ↘ NOT_FOUND → retried with exponential backoff
MATCHED → CHECKING → LOST      ← hidden until re-confirmed
```

On startup the app preloads the top trending titles across all categories and runs each through the resolver. Only `MATCHED` content appears in the UI. `LOST` content is retried on a backoff schedule and flips back to `MATCHED` automatically when it reappears.

### Stream Resolution

When a user plays a title:
1. Backend looks up the confirmed source
2. Headless browser resolves the embed to a raw `.m3u8` stream
3. HLS stream is proxied through the backend to the player
4. Subtitles are extracted and passed to hls.js

### Content Categories

| Category | Source |
|---|---|
| Trending | TMDB `/trending/all/day` |
| Anime | TMDB Discover — animation genre + JP origin |
| K-Drama | TMDB Discover — KR origin |
| C-Drama | TMDB Discover — CN origin |
| J-Drama | TMDB Discover — JP origin, non-anime |

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/content/trending` | Matched trending content |
| `GET` | `/content/{id}` | Content detail |
| `GET` | `/content/{id}/seasons` | Season list |
| `GET` | `/content/{id}/episodes` | Episode list |
| `POST` | `/content/stream/start` | Start stream job |
| `GET` | `/content/stream/status/{job_id}` | Poll stream job |
| `GET` | `/search/?q=` | Search matched content |
| `GET` | `/content/admin/health` | System health + resolver status |
| `GET` | `/auth/google` | Google OAuth login |
| `GET` | `/auth/google/callback` | OAuth callback |
| `GET` | `/auth/me` | Current user |

---

## Deployment

Deployed on Render. Requires:
- Web service (backend)
- Static site (frontend)
- PostgreSQL
- Redis

Set `APP_ENV=production` and fill in `CORS_ORIGINS` and `BACKEND_URL` with your Render URLs before deploying.

**Scaling path** — to move from free tier to a proper worker setup:
```
AVAILABILITY_DRIVER=arq
```
Then add a background worker service. No code changes required.

---

## Health Check

```bash
curl https://your-api.onrender.com/content/admin/health
```

```json
{
  "scraper_healthy": true,
  "scraper_latency_ms": 620,
  "availability": {
    "matched": 30,
    "not_found": 30
  }
}
```

---

© 2026 chaszuu. All rights reserved.

made with ❤️ by chaszuu
