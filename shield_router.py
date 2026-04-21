"""
UMEQAM Shield Mobile — DNS роутер
Добавь в main.py:
    from shield_router import router as shield_router
    app.include_router(shield_router)
"""

import os
import secrets
import httpx
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse, HTMLResponse, Response
from pydantic import BaseModel
import asyncpg

router = APIRouter(prefix="/shield", tags=["Shield"])

# ── БД ────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
ADMIN_KEY    = os.getenv("SHIELD_ADMIN_KEY", "change_me")

async def get_db():
    return await asyncpg.connect(DATABASE_URL, ssl="require")

# ── Список трекеров (встроен, без внешних API) ─────────────
TRACKER_DOMAINS = {
    # Аналитика
    "analytics.google.com", "www.google-analytics.com", "ssl.google-analytics.com",
    "stats.g.doubleclick.net", "ad.doubleclick.net", "googletagmanager.com",
    "googletagservices.com", "pagead2.googlesyndication.com",
    # Facebook / Meta
    "graph.facebook.com", "connect.facebook.net", "pixel.facebook.com",
    "an.facebook.com", "edge-mqtt.facebook.com",
    # Yandex / Mail.ru
    "mc.yandex.ru", "mc.yandex.com", "top.mail.ru", "counter.yadro.ru",
    # Реклама
    "ads.twitter.com", "static.ads-twitter.com",
    # Шпионские SDK
    "appsflyer.com", "adjust.com", "branch.io", "kochava.com",
    "flurry.com", "mixpanel.com", "amplitude.com", "segment.io", "segment.com",
    "intercom.io", "hotjar.com", "fullstory.com",
    "newrelic.com", "nr-data.net", "sentry.io", "bugsnag.com",
    # Xiaomi телеметрия
    "data.mistat.xiaomi.com", "sdkconfig.ad.xiaomi.com",
    "tracking.miui.com", "api.ad.xiaomi.com",
    # Сборщики данных
    "scorecardresearch.com", "quantserve.com", "comscore.com",
    "chartbeat.com", "moatads.com",
    # DataDog (из твоего Shield скрина)
    "browser-intake-us5-datadoghq.com", "browser-intake-datadoghq.com",
    "logs.browser-intake-datadoghq.com",
}

def classify_domain(domain: str) -> tuple[bool, str]:
    d = domain.lower().lstrip("www.")
    if d not in TRACKER_DOMAINS:
        return False, "ok"
    if any(x in d for x in ["facebook", "mistat", "xiaomi", "datadog"]):
        return True, "spy"
    if any(x in d for x in ["analytics", "adjust", "appsflyer", "amplitude", "mixpanel"]):
        return True, "tracker"
    return True, "ads"

# ── Схемы ─────────────────────────────────────────────────────
class CreateClientRequest(BaseModel):
    name: Optional[str] = "Клиент"
    phone: Optional[str] = ""

class ToggleClientRequest(BaseModel):
    token: str
    active: bool

# ── Хелпер: проверка admin key ────────────────────────────────
def check_admin(x_admin_key: Optional[str]):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="forbidden")

# ── ADMIN: создать клиента ────────────────────────────────────
@router.post("/admin/create")
async def admin_create(
    req: CreateClientRequest,
    request: Request,
    x_admin_key: Optional[str] = Header(None)
):
    check_admin(x_admin_key)
    token = secrets.token_hex(12)  # 24 символа
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO shield_clients(token, name, phone) VALUES($1, $2, $3)",
            token, req.name, req.phone
        )
    finally:
        await db.close()
    host = request.headers.get("host", "umeqam-api-production.up.railway.app")
    dns_url = f"https://{host}/shield/dns/{token}"
    return {"token": token, "dns_url": dns_url, "name": req.name, "phone": req.phone}

# ── ADMIN: список клиентов ────────────────────────────────────
@router.get("/admin/clients")
async def admin_clients(x_admin_key: Optional[str] = Header(None)):
    check_admin(x_admin_key)
    db = await get_db()
    try:
        rows = await db.fetch(
            "SELECT token, name, phone, active, created_at, last_seen, blocked_count "
            "FROM shield_clients ORDER BY created_at DESC"
        )
    finally:
        await db.close()
    return [dict(r) for r in rows]

# ── ADMIN: отключить / включить ───────────────────────────────
@router.post("/admin/toggle")
async def admin_toggle(
    req: ToggleClientRequest,
    x_admin_key: Optional[str] = Header(None)
):
    check_admin(x_admin_key)
    db = await get_db()
    try:
        await db.execute(
            "UPDATE shield_clients SET active=$1 WHERE token=$2",
            req.active, req.token
        )
    finally:
        await db.close()
    return {"ok": True, "token": req.token, "active": req.active}

# ── CLIENT: статистика ────────────────────────────────────────
@router.get("/stats/{token}")
async def client_stats(token: str):
    db = await get_db()
    try:
        client = await db.fetchrow(
            "SELECT * FROM shield_clients WHERE token=$1", token
        )
        if not client or not client["active"]:
            raise HTTPException(status_code=403, detail="invalid_token")
        total   = await db.fetchval("SELECT COUNT(*) FROM shield_logs WHERE token=$1", token)
        blocked = await db.fetchval("SELECT COUNT(*) FROM shield_logs WHERE token=$1 AND blocked=TRUE", token)
        recent  = await db.fetch(
            "SELECT domain, category, blocked, ts FROM shield_logs "
            "WHERE token=$1 ORDER BY ts DESC LIMIT 20", token
        )
    finally:
        await db.close()
    return {
        "total":   total,
        "blocked": blocked,
        "recent":  [dict(r) for r in recent],
        "since":   client["created_at"].isoformat() if client["created_at"] else None,
    }

# ── DNS-over-HTTPS (JSON формат) ─────────────────────────────
@router.get("/dns/{token}")
async def doh_get(token: str, request: Request):
    name = request.query_params.get("name", "").lower().rstrip(".")
    qtype = request.query_params.get("type", "A")

    db = await get_db()
    try:
        client = await db.fetchrow(
            "SELECT active FROM shield_clients WHERE token=$1", token
        )
        if not client or not client["active"]:
            return JSONResponse({"Status": 3, "Question": [], "Answer": []}, status_code=403)

        # Обновить last_seen асинхронно
        await db.execute(
            "UPDATE shield_clients SET last_seen=NOW() WHERE token=$1", token
        )

        if not name:
            return JSONResponse({"Status": 1, "Question": [], "Answer": []})

        blocked, category = classify_domain(name)

        # Логируем
        await db.execute(
            "INSERT INTO shield_logs(token, domain, blocked, category) VALUES($1,$2,$3,$4)",
            token, name, blocked, category
        )

        if blocked:
            await db.execute(
                "UPDATE shield_clients SET blocked_count=blocked_count+1 WHERE token=$1", token
            )
            return JSONResponse({
                "Status": 3,  # NXDOMAIN
                "TC": False, "RD": True, "RA": True, "AD": False, "CD": False,
                "Question": [{"name": name, "type": 1}],
                "Answer": []
            })
    finally:
        await db.close()

    # Разрешаем через Cloudflare (серверная сторона)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client_http:
            resp = await client_http.get(
                f"https://cloudflare-dns.com/dns-query",
                params={"name": name, "type": qtype},
                headers={"Accept": "application/dns-json"}
            )
        return JSONResponse(resp.json())
    except Exception:
        return JSONResponse({"Status": 2, "Question": [], "Answer": []}, status_code=502)

# ── DoH бинарный (RFC 8484) ───────────────────────────────────
@router.post("/dns/{token}")
async def doh_post(token: str, request: Request):
    db = await get_db()
    try:
        client = await db.fetchrow(
            "SELECT active FROM shield_clients WHERE token=$1", token
        )
        if not client or not client["active"]:
            return Response(status_code=403)
    finally:
        await db.close()
    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            resp = await c.post(
                "https://cloudflare-dns.com/dns-query",
                content=body,
                headers={"Content-Type": "application/dns-message"}
            )
        return Response(content=resp.content, media_type="application/dns-message")
    except Exception:
        return Response(status_code=502)

# ── PWA manifest ──────────────────────────────────────────────
@router.get("/manifest.json")
async def manifest():
    return {
        "name": "UMEQAM Shield",
        "short_name": "Shield",
        "start_url": "/shield/",
        "display": "standalone",
        "background_color": "#0a0a0f",
        "theme_color": "#0a0a0f",
        "icons": [{"src": "/shield/icon.png", "sizes": "192x192", "type": "image/png"}]
    }
