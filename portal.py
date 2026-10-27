"""
Phase 2, Step 1: the hand-off from the Anthem to the RNL Corporate Portal.

What happens:
  1. (No pause: the welcome follows the clean sweep immediately.)
  2. The bot sends a "Welcome to RNL" message with an [Open Corporate Portal] button.
  3. Tapping the button opens the portal (a Telegram Mini App) inside Telegram.
     The portal (portal.html) holds the six sequential sections.
"""
import os
import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiohttp import web

log = logging.getLogger("repellano.portal")

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


async def portal_page(request: web.Request) -> web.Response:
    return web.Response(
        text=PORTAL_HTML,
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )
