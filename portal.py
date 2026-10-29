"""
Phase 2, Step 1: the hand-off from the Anthem to the RNL Corporate Portal.

What happens:
  1. (No pause: the welcome follows the clean sweep immediately.)
  2. The bot sends a "Welcome to RNL" message with an [Open Corporate Portal] button.
  3. Tapping the button opens the portal (a Telegram Mini App) inside Telegram.
     The portal (portal.html) holds the six sequential sections.
"""
import os
import time
import asyncio
import hashlib
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiohttp import web

import content
import db
import tgauth

log = logging.getLogger("repellano.portal")

# bot.py sets this to an async function(user_id) that runs once when a member finishes all six sections
on_complete = None

PAUSE_SECONDS = 0  # no pause: the welcome appears the instant the clean sweep ends


def portal_url() -> str:
    """Public address of the portal page. Telegram requires https."""
    explicit = os.getenv("PORTAL_URL", "").strip()
    if explicit:
        return explicit
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    return f"{render_url}/portal" if render_url else ""


WELCOME_TEXT = (
    "🏛 <b>Welcome to Repellano Nigeria Limited (RNL)</b>\n\n"
    "Tap the button below to open our Corporate Portal and get to know us."
)


async def handoff(bot: Bot, user_id: int, session: dict, is_current) -> None:
    """Called by bot.py right after the Anthem clean sweep.
    `is_current()` tells us whether this member is still on the same run; if they
    pressed /start during the pause, this old run stops and sends nothing."""
    session["phase"] = "portal_wait"

    if PAUSE_SECONDS > 0:
        try:
            await bot.send_chat_action(chat_id=user_id, action="typing")
        except Exception:
            pass
        await asyncio.sleep(PAUSE_SECONDS)
    if not is_current():
        log.info("Member %s restarted during the pause; portal welcome skipped.", user_id)
        return

    url = portal_url()
    if url.startswith("https://"):
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏛 Open Corporate Portal", web_app=WebAppInfo(url=url))
        ]])
        text = WELCOME_TEXT
    else:
        log.error("PORTAL_URL is not set to an https address; portal button not shown.")
        markup = None
        text = WELCOME_TEXT + "\n\n<i>(The portal is being prepared. Please try again shortly.)</i>"

    msg = await bot.send_message(
        chat_id=user_id, text=text, reply_markup=markup, parse_mode=ParseMode.HTML
    )
    if not is_current():
        # restarted while the message was being sent: remove it again
        try:
            await bot.delete_message(chat_id=user_id, message_id=msg.message_id)
        except Exception:
            pass
        return
    session["to_wipe"] = [msg.message_id]  # so a later /start can wipe it
    session["phase"] = "portal"


# --- THE PORTAL PAGE (portal.html sits next to this file) ---
_FALLBACK_HTML = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'></head>"
    "<body style='font-family:sans-serif;text-align:center;padding:40px'>"
    "<h2>RNL Corporate Portal</h2><p>The portal page is being prepared. Please try again shortly.</p>"
    "</body></html>"
)


def _load_portal_html() -> str:
    path = Path(__file__).with_name("portal.html")
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        log.error("portal.html not found next to portal.py; showing the fallback page.")
        return _FALLBACK_HTML


PORTAL_HTML = _load_portal_html()
_PORTAL_ETAG = '"' + hashlib.sha1(PORTAL_HTML.encode("utf-8")).hexdigest()[:16] + '"'


async def portal_page(request: web.Request) -> web.Response:
    """The page is compressed and tagged with an ETag, so a returning member's phone only
    re-downloads it when it has really changed (a quick 304 answer otherwise)."""
    headers = {"ETag": _PORTAL_ETAG, "Cache-Control": "no-cache"}
    if request.headers.get("If-None-Match") == _PORTAL_ETAG:
        return web.Response(status=304, headers=headers)
    resp = web.Response(text=PORTAL_HTML, content_type="text/html", headers=headers)
    try:
        resp.enable_compression()
    except Exception:
        pass
    return resp


# --- PROGRESS AND CONTENT API (used by portal.html; every call is checked against Telegram's signature) ---
def _json(data: dict, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, headers={"Cache-Control": "no-store"})


def _member(request: web.Request):
    token = os.getenv("BOT_TOKEN", "").strip()
    return tgauth.validate_init_data(request.headers.get("X-Telegram-Init-Data", ""), token)


def _unlocked(completed: int) -> dict:
    """The text of every section this member has unlocked: the ones already read, plus the next one."""
    top = min(completed, content.TOTAL - 1)
    return {str(i): {"html": content.SECTIONS[i]["html"]} for i in range(top + 1)}


async def api_get_progress(request: web.Request) -> web.Response:
    t0 = time.monotonic()
    try:
        return await _get_progress(request)
    finally:
        log.info("GET /api/progress took %d ms", (time.monotonic() - t0) * 1000)


async def _get_progress(request: web.Request) -> web.Response:
    user = _member(request)
    if not user:
        return _json({"error": "unauthorized"}, 401)
    if not db.enabled():
        # No database configured (testing only): nothing can be enforced, so everything is shown.
        return _json({"enabled": False, "sections": _unlocked(content.TOTAL)})
    try:
        anthem_done, completed = await db.member_state(user["id"])
    except Exception:
        log.exception("member_state failed")
        return _json({"error": "busy"}, 503)
    if not anthem_done:
        return _json({"enabled": True, "gate": "anthem"})
    return _json({"enabled": True, "completed": completed, "sections": _unlocked(completed)})


async def api_mark_read(request: web.Request) -> web.Response:
    user = _member(request)
    if not user:
        return _json({"error": "unauthorized"}, 401)
    if not db.enabled():
        return _json({"enabled": False})
    try:
        body = await request.json()
        section = int(body.get("section"))
    except Exception:
        return _json({"error": "bad request"}, 400)
    if not 0 <= section < content.TOTAL:
        return _json({"error": "bad request"}, 400)
    try:
        anthem_done, before = await db.member_state(user["id"])
        if not anthem_done:
            return _json({"enabled": True, "gate": "anthem"})
        completed = await db.advance_progress(user["id"], section)
        if before < content.TOTAL <= completed and on_complete is not None:
            asyncio.create_task(_run_on_complete(user["id"]))
    except Exception:
        log.exception("advance_progress failed")
        return _json({"error": "busy"}, 503)
    sections = {}
    if completed < content.TOTAL:   # hand over the section that has just been unlocked
        sections[str(completed)] = {"html": content.SECTIONS[completed]["html"]}
    return _json({"enabled": True, "completed": completed, "sections": sections})


async def _run_on_complete(user_id: int) -> None:
    try:
        await on_complete(user_id)
    except Exception:
        log.exception("on_complete failed for %s", user_id)
