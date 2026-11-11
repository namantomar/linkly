"""Linkly — URL shortener API with click analytics.

Endpoints
---------
POST   /api/links              create a short link
GET    /api/links              list links (newest first, with click counts)
GET    /api/links/{code}/stats click analytics for one link
DELETE /api/links/{code}      delete a link
GET    /{code}                 redirect to the long URL (records a click)
GET    /                       built-in web UI
"""

import secrets
import string
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Click, Link
from .schemas import LinkCreate, LinkOut, LinkStats, ReferrerStat

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

_ALPHABET = string.ascii_letters + string.digits


def _generate_code(length: int = 6) -> str:
    """Random URL-safe short code."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def _short_url(request: Request, code: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/{code}"


def _link_out(request: Request, link: Link, click_count: int) -> LinkOut:
    return LinkOut(
        code=link.code,
        long_url=link.long_url,
        short_url=_short_url(request, link.code),
        created_at=link.created_at,
        expires_at=link.expires_at,
        click_count=click_count,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Linkly",
    description="A URL shortener API with click analytics.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def read_root():
    """Serve the built-in web UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/links", response_model=LinkOut, status_code=201)
def create_link(
    payload: LinkCreate, request: Request, db: Session = Depends(get_db)
):
    """Create a short link from a long URL.

    Optional ``custom_alias`` reserves a specific short code (409 if taken),
    and ``expires_in_days`` sets a lifetime after which redirects return 410.
    """
    code = payload.custom_alias
    if code is not None:
        if db.query(Link).filter(Link.code == code).first():
            raise HTTPException(
                status_code=409, detail=f"alias '{code}' is already taken"
            )
    else:
        # Generate a random code, retrying on the (very unlikely) collision.
        for _ in range(10):
            candidate = _generate_code()
            if not db.query(Link).filter(Link.code == candidate).first():
                code = candidate
                break
        else:  # pragma: no cover - collision loop exhausted
            raise HTTPException(status_code=500, detail="could not generate a code")

    expires_at = None
    if payload.expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=payload.expires_in_days
        )

    link = Link(
        code=code, long_url=str(payload.long_url), expires_at=expires_at
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return _link_out(request, link, click_count=0)


@app.get("/api/links", response_model=list[LinkOut])
def list_links(request: Request, db: Session = Depends(get_db)):
    """List all links, newest first, each with its click count."""
    links = db.query(Link).order_by(Link.created_at.desc(), Link.id.desc()).all()
    counts = dict(
        db.query(Click.link_id, func.count(Click.id))
        .group_by(Click.link_id)
        .all()
    )
    return [_link_out(request, link, counts.get(link.id, 0)) for link in links]


@app.get("/api/links/{code}/stats", response_model=LinkStats)
def link_stats(code: str, db: Session = Depends(get_db)):
    """Click analytics for one link: total, per-day, and top referrers."""
    link = db.query(Link).filter(Link.code == code).first()
    if link is None:
        raise HTTPException(status_code=404, detail="link not found")

    clicks = db.query(Click).filter(Click.link_id == link.id).all()
    clicks_per_day = dict(
        sorted(Counter(c.clicked_at.date().isoformat() for c in clicks).items())
    )
    top_referrers = [
        ReferrerStat(referrer=referrer, clicks=count)
        for referrer, count in Counter(
            c.referrer or "direct" for c in clicks
        ).most_common(5)
    ]
    return LinkStats(
        code=link.code,
        long_url=link.long_url,
        total_clicks=len(clicks),
        clicks_per_day=clicks_per_day,
        top_referrers=top_referrers,
    )


@app.delete("/api/links/{code}", status_code=204)
def delete_link(code: str, db: Session = Depends(get_db)):
    """Delete a link (and its recorded clicks)."""
    link = db.query(Link).filter(Link.code == code).first()
    if link is None:
        raise HTTPException(status_code=404, detail="link not found")
    db.delete(link)
    db.commit()
    return None


@app.get("/{code}")
def redirect_link(code: str, request: Request, db: Session = Depends(get_db)):
    """Redirect to the long URL and record the click.

    Expired links return 410 Gone; unknown codes return 404.
    """
    link = db.query(Link).filter(Link.code == code).first()
    if link is None:
        raise HTTPException(status_code=404, detail="link not found")
    if link.is_expired:
        raise HTTPException(status_code=410, detail="link has expired")

    db.add(
        Click(
            link_id=link.id,
            referrer=request.headers.get("referer"),
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
    return RedirectResponse(url=link.long_url, status_code=307)
