# Linkly

A URL shortener API with click analytics. Create short links, redirect
through them, and see exactly how each link is performing — total clicks,
clicks per day, and top referrers.

## Tech stack

- **Python 3.12** + **FastAPI** — async-ready REST API
- **SQLAlchemy** + **SQLite** — file-based persistence, no setup
- **Pydantic** — request validation
- **pytest** + **httpx** — end-to-end API tests
- **Docker** — one-command deployment

## Features

- Shorten any URL, with an optional custom alias and optional expiry in days
- `307` redirects that record every click (timestamp, referrer, user-agent)
- Click analytics per link: total clicks, clicks per day, top referrers
- List links with click counts, newest first
- Delete links
- Built-in web UI (plain HTML/CSS + `fetch`, no framework)
- Validation: invalid URLs rejected, duplicate aliases return `409`,
  expired links return `410` on redirect

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 for the web UI, or
http://localhost:8000/docs for the interactive API docs.

The SQLite database (`linkly.db`) is created automatically on first run.

## Docker

```bash
docker build -t linkly .
docker run -p 8000:8000 linkly
```

## API endpoints

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| `POST` | `/api/links` | Create a short link |
| `GET` | `/api/links` | List links with click counts (newest first) |
| `GET` | `/api/links/{code}/stats` | Click analytics for one link |
| `DELETE` | `/api/links/{code}` | Delete a link |
| `GET` | `/{code}` | Redirect to the long URL (records a click) |
| `GET` | `/` | Built-in web UI |

### Create a link

```bash
curl -X POST http://localhost:8000/api/links \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://example.com/a/very/long/url", "custom_alias": "my-link", "expires_in_days": 30}'
```

```json
{
  "code": "my-link",
  "long_url": "https://example.com/a/very/long/url",
  "short_url": "http://localhost:8000/my-link",
  "created_at": "2026-11-10T19:00:00Z",
  "expires_at": "2026-12-10T19:00:00Z",
  "click_count": 0
}
```

### Stats

```bash
curl http://localhost:8000/api/links/my-link/stats
```

```json
{
  "code": "my-link",
  "long_url": "https://example.com/a/very/long/url",
  "total_clicks": 12,
  "clicks_per_day": {"2026-11-10": 12},
  "top_referrers": [{"referrer": "https://google.com", "clicks": 8}]
}
```

## Project structure

```
linkly/
├── app/
│   ├── main.py          # FastAPI app, routes, redirect + click recording
│   ├── models.py        # SQLAlchemy models: Link, Click
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── database.py      # SQLite engine, session, get_db dependency
│   └── static/
│       ├── index.html   # Built-in web UI
│       └── styles.css   # Plain CSS for the UI
├── tests/
│   ├── conftest.py      # Isolated in-memory DB fixtures
│   └── test_links.py    # API tests (create, redirect, stats, errors)
├── requirements.txt
├── Dockerfile
└── README.md
```

## Tests

```bash
pytest -v
```

## License

MIT — see [LICENSE](LICENSE).
