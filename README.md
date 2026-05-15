# nud

A distributed streaming service with JIT (just-in-time) video processing.

Content metadata is sourced from TMDB and matched against live stream sources at request time. Only confirmed-available titles are surfaced to users.

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
│   ├── scrapers/       # Stream resolvers
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

On startup the app preloads the top trending titles across all categories (trending, anime, kdrama, cdrama, jdrama) and runs each through the scraper. Only `MATCHED` content appears in the UI.

### Stream Resolution

When a user plays a title:
1. The backend looks up the confirmed source slug
2. Playwright resolves the embed URL to a raw `.m3u8` stream
3. The HLS stream is proxied through the backend to the player
4. Subtitles are extracted and passed to hls.js

### Categories

| Category | Source |
|---|---|
| Trending | TMDB `/trending/all/day` |
| Anime | TMDB `/discover/tv` — genre 16 + JP origin |
| K-Drama | TMDB `/discover/tv` — KR origin |
| C-Drama | TMDB `/discover/tv` — CN origin |
| J-Drama | TMDB `/discover/tv` — JP origin, non-anime |

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
| `GET` | `/content/admin/health` | System health + scraper status |
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

made with ❤️ by chaszuu
