<div align="center">

# 🔍 LinkLens — Link Analytics Platform

**A distributed, fault-tolerant URL shortener with an async analytics pipeline — built to study and demonstrate production system design.**

![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)

</div>

---

## 🧠 The Core Idea

Most URL shortener tutorials show you how to store a link and redirect. LinkLens is different — it's built around a question:

> **How does a real system handle millions of redirects a day without collapsing under its own analytics?**

The answer is decoupling. The redirect path is kept ruthlessly fast — Redis cache lookup, enqueue a click event, return a 302. The *analytics* — writing to Postgres, enriching with geolocation and device data — happen asynchronously in a background worker. The user never waits for the database.

Every design decision here maps to a concept you'd find in systems like Bitly, Dub.co, or any high-throughput link service.

---

## 🏗️ Architecture

```
                        ┌──────────────────────────────────┐
                        │           Client Request          │
                        └─────────────┬────────────────────┘
                                      │
                                      ▼
                        ┌─────────────────────────┐
                        │       FastAPI Server      │
                        │     (Uvicorn ASGI)        │
                        └────┬──────────┬──────────┘
                             │          │
               Cache Lookup  │          │  Cache Miss
                             ▼          ▼
                    ┌──────────────┐  ┌──────────────────────┐
                    │    Redis      │  │    PostgreSQL         │
                    │  (Hot URLs)   │  │  (Source of Truth)    │
                    │  TTL: 1 hour  │  │  B-tree on short_code │
                    └──────┬───────┘  └──────────────────────┘
                           │
                           ▼
                    ┌──────────────────┐
                    │   Redis Queue     │  ← Enqueue click event
                    │   (RQ / async)    │    redirect returns here ✅
                    └──────────┬───────┘
                               │
                               ▼
                    ┌──────────────────────────────┐
                    │        Worker Process          │
                    │  - Writes Click to Postgres    │
                    │  - Enriches with device + geo  │
                    │  - Increments click counter    │
                    └──────────────────────────────┘
```

### Two-Layer Read Architecture

The redirect path has two layers of data access, each chosen for a specific reason:

```
Layer 1 — Redis (O(1) key lookup, sub-millisecond)
    Redis.get("aB3xKp")
         │
    HIT  └──────────────────────────► 302 Redirect  ✅ (< 1ms)
         │
    MISS ▼
Layer 2 — PostgreSQL (B-tree index on short_code)
    SELECT original_url WHERE short_code = 'aB3xKp'
         │
         └──► store in Redis (TTL: 1hr) ──► 302 Redirect
```

**Why B-tree and not hash indexing?**
The `clicks` table is queried almost exclusively with range conditions — `WHERE clicked_at BETWEEN ...`, `GROUP BY date(clicked_at)`. Hash indexes are O(1) for equality but **can't serve range queries**. B-tree supports both equality lookups *and* ordered range scans, making it the correct choice for time-series analytics aggregations.

---

## 🚀 Features

### ✅ Implemented

| Feature | Detail |
|---|---|
| **URL Shortening** | Unique 6-character alphanumeric codes with guaranteed collision handling |
| **Two-Layer Read Path** | Redis cache-aside → Postgres B-tree fallback on miss |
| **Async Analytics Pipeline** | Click events enqueued to Redis Queue; worker enriches and persists asynchronously |
| **Click Enrichment** | Device type (mobile/desktop) + browser parsed from User-Agent header |
| **IP Geolocation** | Country detection via MaxMind GeoIP2 (library installed, integration active) |
| **Aggregated Stats API** | Per-link breakdown: clicks/day, device split, browser split, geo distribution |
| **Dockerized Infrastructure** | One command spins up Postgres + Redis |
| **Auto API Docs** | Swagger UI at `/docs`, ReDoc at `/redoc` |

### 🔧 Roadmap

| Feature | System Design Concept |
|---|---|
| **JWT Authentication** | Stateless auth — access + refresh token pattern |
| **User Ownership** | Multi-tenant data isolation per user |
| **Rate Limiting** | Sliding window counter in Redis — per-user request throttling |
| **React Dashboard** | Real-time analytics UI |
| **Custom Short Codes** | Vanity URL support |
| **QR Code Generation** | Per-link QR export |
| **Horizontal Scaling** | Stateless app layer + shared Redis/Postgres — load balancer ready |
| **Deployment** | Dockerized production deploy on Fly.io / Railway |

---

## ⚙️ Key Engineering Decisions

### Why Redis for caching, not an in-memory dict?
An in-memory dict would break the moment you run two app instances behind a load balancer — each process has its own dict. Redis is a shared, external cache. Every instance reads from and writes to the same store, making the system horizontally scalable from day one.

### Why decouple click logging into a queue?
The naive approach: on every redirect, write a `Click` row to Postgres, then redirect. This ties redirect latency directly to database write speed. Under high traffic, a slow Postgres write blocks the user's redirect.

The queue approach: enqueue a lightweight event to Redis (< 1ms), redirect immediately. A separate worker process picks up the event and does the expensive work — DB write, geo enrichment, counter update — with no impact on the user's experience.

### Why B-tree indexes on the `clicks` table?
Analytics queries on `clicks` are range-heavy:
```sql
-- clicks per day
SELECT date(clicked_at), COUNT(*) FROM clicks
WHERE short_code = 'aB3xKp'
GROUP BY date(clicked_at);
```
Hash indexes are O(1) for `WHERE col = val` but **cannot serve `GROUP BY date(...)` or `ORDER BY` efficiently**. B-tree indexes support both — equality lookup *and* ordered range scans — making them the right default for time-series data.

### Why `short_code` is a VARCHAR with a UNIQUE B-tree index?
Every redirect is a point lookup: `WHERE short_code = 'aB3xKp'`. The B-tree on `short_code` makes this O(log n) regardless of how many rows exist. The UNIQUE constraint enforces collision safety at the database level, not just application level.

---

## 📡 API Reference

### `POST /shorten/`
Shorten a URL and receive a unique short code.

**Request:**
```json
{ "original_url": "https://example.com/very/long/path?with=params" }
```
**Response:**
```json
{
  "original_url": "https://example.com/very/long/path?with=params",
  "short_url": "http://127.0.0.1:8000/aB3xKp"
}
```

---

### `GET /{code}`
Redirect to the original URL. Enqueues a click event for async processing.

- `302 Redirect`
- Served from Redis on cache hit (< 1ms on hot paths)
- Falls back to Postgres B-tree lookup on miss, then back-fills cache

---

### `GET /stats/{code}`
Aggregated analytics for a short link.

```json
{
  "short_code": "aB3xKp",
  "total_clicks": 342,
  "clicks_per_day": [
    { "date": "2025-06-20", "count": 120 },
    { "date": "2025-06-21", "count": 222 }
  ],
  "device_stats": [
    { "device": "mobile", "count": 198 },
    { "device": "desktop", "count": 144 }
  ],
  "browser_stats": [
    { "browser": "Chrome", "count": 280 },
    { "browser": "Safari", "count": 62 }
  ],
  "country_stats": [
    { "country": "IN", "count": 300 },
    { "country": "US", "count": 42 }
  ]
}
```

---

### `GET /ping`
Health check.
```json
{ "status": "ok" }
```

---

## 🗃️ Data Models

### `urls` table
```
id            INTEGER   PRIMARY KEY
original_url  TEXT      NOT NULL
short_code    VARCHAR   UNIQUE — B-tree index (point lookup on redirect)
created_at    DATETIME
clicks        INTEGER   DEFAULT 0  (denormalized counter for fast reads)
```

### `clicks` table
```
id          INTEGER   PRIMARY KEY
short_code  VARCHAR   B-tree index (equality filter in analytics queries)
clicked_at  DATETIME  B-tree index (range scans for clicks/day aggregation)
country     VARCHAR
device      VARCHAR   (mobile | desktop)
browser     VARCHAR   (Chrome | Safari | Firefox ...)
```

> **Note on the denormalized `clicks` counter:** `urls.clicks` is a fast-path counter incremented on every redirect. It duplicates data from the `clicks` table by design — serving the "total clicks" stat without a `COUNT(*)` full scan.

---

## ⚙️ Local Setup

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- Python 3.11+

### 1. Clone the repo
```bash
git clone https://github.com/your-username/linklens.git
cd linklens
```

### 2. Set up virtual environment
```bash
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env with your values
```

### 5. Start infrastructure (Postgres + Redis)
```bash
docker compose up -d
```

### 6. Run the API server
```bash
uvicorn main:app --reload
```

### 7. Run the analytics worker (separate terminal)
```bash
python worker.py
```

### 8. Open interactive API docs
```
http://127.0.0.1:8000/docs
```

---

## 📦 Project Structure

```
linklens/
├── main.py              # FastAPI app — routes + Redis cache logic
├── models.py            # SQLAlchemy ORM (URL, Click)
├── database.py          # Engine + session factory
├── worker_config.py     # RQ Queue + Redis connection
├── tasks.py             # Background task: log_click()
├── worker.py            # Worker process entry point
├── docker-compose.yml   # Postgres + Redis containers
├── .env                 # Secrets (gitignored)
├── .env.example         # Env template
└── requirements.txt     # Python dependencies
```

---

## 🧩 System Design Concepts

| Concept | Where |
|---|---|
| **Cache-Aside Pattern** | Redis in front of Postgres on all redirect reads |
| **TTL-based Eviction** | Cached URLs expire after 1 hour — no manual invalidation needed |
| **Async Write Decoupling** | Click logging via Redis Queue — redirect hot path never touches Postgres directly |
| **B-tree Index Selection** | Chosen over hash for range query support on `clicked_at` |
| **Denormalized Counter** | `urls.clicks` avoids full-table `COUNT(*)` for total click reads |
| **Collision-safe ID Gen** | Loop-until-unique short code generation, enforced at DB level too |
| **Stateless Application** | No session state in the app — safe to run multiple instances behind a load balancer |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| Database | PostgreSQL 15 |
| ORM | SQLAlchemy 2.0 |
| Cache | Redis 7 |
| Job Queue | RQ (Redis Queue) |
| Containerization | Docker + Docker Compose |
| UA Parsing | `user-agents` |
| Geolocation | MaxMind GeoIP2 |
| Validation | Pydantic v2 |

---

<div align="center">

Built to learn system design by building — not by reading about it.

</div>
