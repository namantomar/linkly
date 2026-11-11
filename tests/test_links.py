"""End-to-end tests for the Linkly API."""

from datetime import datetime, timedelta, timezone

from app.models import Link


def _create(client, long_url="https://example.com/some/very/long/page", **extra):
    payload = {"long_url": long_url}
    payload.update(extra)
    return client.post("/api/links", json=payload)


def test_create_link_returns_short_url(client):
    response = _create(client)
    assert response.status_code == 201
    data = response.json()
    assert data["code"]
    assert data["long_url"] == "https://example.com/some/very/long/page"
    assert data["short_url"].endswith(f"/{data['code']}")
    assert data["click_count"] == 0
    assert data["expires_at"] is None


def test_create_link_with_custom_alias_and_expiry(client):
    response = _create(client, custom_alias="my-link", expires_in_days=7)
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "my-link"
    assert data["expires_at"] is not None


def test_create_link_rejects_invalid_url(client):
    response = _create(client, long_url="not-a-url")
    assert response.status_code == 422


def test_create_link_rejects_duplicate_alias(client):
    assert _create(client, custom_alias="taken").status_code == 201
    response = _create(
        client, long_url="https://example.com/other", custom_alias="taken"
    )
    assert response.status_code == 409
    assert "taken" in response.json()["detail"]


def test_create_link_rejects_bad_alias(client):
    response = _create(client, custom_alias="has spaces!")
    assert response.status_code == 422


def test_redirect_records_click(client):
    code = _create(client).json()["code"]

    response = client.get(
        f"/{code}",
        headers={"referer": "https://google.com", "user-agent": "pytest"},
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com/some/very/long/page"

    stats = client.get(f"/api/links/{code}/stats").json()
    assert stats["total_clicks"] == 1
    today = datetime.now(timezone.utc).date().isoformat()
    assert stats["clicks_per_day"] == {today: 1}
    assert stats["top_referrers"] == [
        {"referrer": "https://google.com", "clicks": 1}
    ]


def test_redirect_unknown_code_returns_404(client):
    response = client.get("/nope123", follow_redirects=False)
    assert response.status_code == 404


def test_list_links_sorted_newest_first_with_click_counts(client):
    first = _create(client, custom_alias="first-link").json()
    second = _create(client, custom_alias="second-link").json()
    client.get(f"/{second['code']}", follow_redirects=False)
    client.get(f"/{second['code']}", follow_redirects=False)

    response = client.get("/api/links")
    assert response.status_code == 200
    links = response.json()
    assert [link["code"] for link in links] == ["second-link", "first-link"]
    assert links[0]["click_count"] == 2
    assert links[1]["click_count"] == 0


def test_stats_for_unknown_link_returns_404(client):
    assert client.get("/api/links/nope123/stats").status_code == 404


def test_delete_link(client):
    code = _create(client).json()["code"]
    assert client.delete(f"/api/links/{code}").status_code == 204
    assert client.get(f"/{code}", follow_redirects=False).status_code == 404
    assert client.delete(f"/api/links/{code}").status_code == 404


def test_expired_link_returns_410(client, db_session):
    # Create a link, then back-date its expiry directly in the test database.
    code = _create(client).json()["code"]
    link = db_session.query(Link).filter(Link.code == code).first()
    link.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    response = client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 410
    assert "expired" in response.json()["detail"]


def test_homepage_serves_ui(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Linkly" in response.text
    assert "shorten-form" in response.text
