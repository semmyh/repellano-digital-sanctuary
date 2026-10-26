"""
Phase 2, Step 1: the hand-off from the Anthem to the RNL Corporate Portal.

What happens:
  1. The clean slate stays empty for 5 seconds (the "pause").
  2. The bot sends a "Welcome to RNL" message with an [Open Corporate Portal] button.
  3. Tapping the button opens the portal (a Telegram Mini App) inside Telegram.
     In this step the portal is a simple branded placeholder page that proves the
     connection works. The six sections arrive in Step 2.
"""
import os
import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiohttp import web

log = logging.getLogger("repellano.portal")

PAUSE_SECONDS = 5


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

    # Show "typing..." during the pause so the empty screen feels intentional
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


# --- PLACEHOLDER PORTAL PAGE (replaced by the real sections in Step 2) ---
PORTAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>RNL Corporate Portal</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root { color-scheme: light dark; }
  body {
    margin: 0; min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; text-align: center;
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    background: var(--tg-theme-bg-color, #0f1722);
    color: var(--tg-theme-text-color, #f1f5f9);
    padding: 24px; box-sizing: border-box;
  }
  .brand { font-size: 28px; font-weight: 700; letter-spacing: 6px; }
  .sub { margin-top: 6px; opacity: .7; font-size: 14px; }
  .spinner {
    width: 38px; height: 38px; margin: 28px auto 0; border-radius: 50%;
    border: 4px solid rgba(128,128,128,.3); border-top-color: var(--tg-theme-button-color, #d4af37);
    animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  #ready { display: none; margin-top: 8px; }
  #ready h2 { margin: 0 0 8px; }
  #ready p { margin: 0; opacity: .8; line-height: 1.5; }
</style>
</head>
<body>
  <div id="loading">
    <div class="brand">REPELLANO</div>
    <div class="sub">Corporate Portal</div>
    <div class="spinner"></div>
  </div>
  <div id="ready">
    <div class="brand">REPELLANO</div>
    <h2 id="hello">Portal connected ✅</h2>
    <p>Your Corporate Portal is working.<br>The six sections will appear here soon.</p>
  </div>
<script>
  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) { tg.ready(); tg.expand(); }
  setTimeout(function () {
    document.getElementById("loading").style.display = "none";
    document.getElementById("ready").style.display = "block";
    try {
      var u = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
      if (u && u.first_name) {
        document.getElementById("hello").textContent = "Portal connected ✅ Welcome, " + u.first_name;
      }
    } catch (e) {}
  }, 2000);
</script>
</body>
</html>
"""


async def portal_page(request: web.Request) -> web.Response:
    return web.Response(
        text=PORTAL_HTML,
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )
