import math
import time
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiohttp import web  # New library to create our free dummy website

# 1. ACTUAL BOT SETUP
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # Put your actual bot token between these quotes
bot = Bot(token=TOKEN)
dp = Dispatcher()

log = logging.getLogger(__name__)

# --- Mock Data Structures ---
CONFIGS = {
    "en": {"duration": 240, "msg_id": 123}, 
    "pidgin": {"duration": 180, "msg_id": 124}
}
USER_SESSIONS = {} 
CHANNEL_ID = -1001234567890  
EN_LYRICS = "📜 *Repellano Anthem \\(English Version\\)*\n\nThis is where your English anthem lyrics go\\."
PIDGIN_LYRICS = "📜 *Repellano Anthem \\(Pidgin Version\\)*\n\nThis is where your Pidgin anthem lyrics go\\."

# ---------------------------------------------------------------------------
# DUMMY WEBSITE FOR RENDER (Keeps the service completely free!)
# ---------------------------------------------------------------------------
async def handle_ping(request):
    return web.Response(text="Repellano Sanctuary Bot is Alive!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render tells us which port to open using process.env.PORT (defaults to 10000)
    import os
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"Dummy web server started on port {port}")

# ---------------------------------------------------------------------------
# KEYBOARDS & INTERFACE BUILDERS
# ---------------------------------------------------------------------------
def onboarding_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Return to Click Here and Unlock Sanctuary", callback_query_data="unlock")]
    ])

def step4_complete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Track Playback Complete", callback_query_data="noop")],
        [InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_query_data="confirm_sweep")]
    ])

# ---------------------------------------------------------------------------
# STEP 2 & 3 HANDLER — LOAD TRACK, LYRICS, & INITIALIZE TIME GATE
# ---------------------------------------------------------------------------
@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    user_id = cb.from_user.id
    
    if user_id not in USER_SESSIONS:
        USER_SESSIONS[user_id] = {"to_wipe": []}
        
    session = USER_SESSIONS[user_id]
    await cb.answer()
    cfg = CONFIGS[lang]

    session["lang"] = lang
    session["duration"] = cfg["duration"]
    session["start_time"] = time.monotonic() 
    session["completed"] = False

    try:
        audio_msg = await bot.copy_message(
            chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"]
        )
        session["to_wipe"].append(audio_msg.message_id)
    except Exception as e:
        log.error("Audio execution failed: %s", e)
        await cb.message.answer("⚠️ Could not load track audio.")
        return

    lyrics_text = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    lyrics_msg = await cb.message.answer(text=lyrics_text, parse_mode=ParseMode.MARKDOWN_V2)
    session["to_wipe"].append(lyrics_msg.message_id)

    instructions_text = (
        f"1️⃣ First, Click Play Button ▶️ Above to Listen Fully \\[{cfg['duration']}s\\]\n\n"
        f"2️⃣ 🔒 Then, Return to Click Here and Unlock Sanctuary"
    )

    instructions_msg = await cb.message.answer(
        text=instructions_text, 
        reply_markup=onboarding_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    session["instructions_msg_id"] = instructions_msg.message_id
    session["to_wipe"].append(instructions_msg.message_id)

# ---------------------------------------------------------------------------
# STEP 3 — THE SMART SHOULDER-TAP GATEKEEPER
# ---------------------------------------------------------------------------
@dp.callback_query(F.data == "unlock")
async def on_unlock(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)

    if not session or session.get("lang") is None:
        await cb.answer("Session expired. Please /start again.", show_alert=True)
        return

    start_time = session.get("start_time", 0.0)
    duration = session.get("duration", 0)
    
    elapsed = time.monotonic() - start_time
    remaining = math.ceil(duration - elapsed)

    if remaining > 0:
        await cb.answer(
            text=f"🔒 Please listen fully to unlock the Sanctuary.\n"
                 f"⏳ {remaining} second(s) remaining.",
            show_alert=True,
        )
        return

    session["completed"] = True
    await cb.answer("✅ Playback verified! Access Granted.", show_alert=False)

    try:
        await bot.edit_message_text(
            chat_id=user_id,
            message_id=session["instructions_msg_id"],
            text="🎉 *Anthem Absorbed Successfully\\!* You can now proceed to wipe the history\\.",
            reply_markup=step4_complete_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        log.error("Failed to morph keyboard down to Step 4: %s", e)

# ---------------------------------------------------------------------------
# MAIN START COUPLING
# ---------------------------------------------------------------------------
async def main():
    # Start the web server first so Render gets its port immediately
    await start_dummy_server()
    # Then start your Telegram bot listener
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
