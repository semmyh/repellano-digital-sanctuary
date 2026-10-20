import math
import time
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiohttp import web

# ---------------------------------------------------------------------------
# 1. CORE BOT CONFIGURATION
# ---------------------------------------------------------------------------
TOKEN = "8642428323:AAEL29Vt0vjnVf98uH785iHl1xB1UD7xRZQ"  # Put your actual bot token between these quotes
bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- Project Assets & Configuration ---
CONFIGS = {
    "en": {"duration": 240, "msg_id": 123},       # 240 seconds
    "pidgin": {"duration": 180, "msg_id": 124}    # 180 seconds
}

USER_SESSIONS = {} 
CHANNEL_ID = -1001234567890  # Replace with your actual channel ID where tracks are securely stored

EN_LYRICS = "📜 *Repellano Anthem \\(English Version\\)*\n\nThis is where your English anthem lyrics text will be displayed\\."
PIDGIN_LYRICS = "📜 *Repellano Anthem \\(Pidgin Version\\)*\n\nThis is where your Pidgin anthem lyrics text will be displayed\\."

# ---------------------------------------------------------------------------
# 2. FREE HOSTING LIFELINE (The Dummy Web Server)
# ---------------------------------------------------------------------------
async def handle_ping(request):
    return web.Response(text="Repellano Sanctuary Engine is Active!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    import os
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"Free layer web node successfully bound to port {port}")

# ---------------------------------------------------------------------------
# 3. INTERFACE BUILDERS
# ---------------------------------------------------------------------------
def language_keyboard() -> InlineKeyboardMarkup:
    """Step 1: Two clean, stacked language selection buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_query_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version", callback_query_data="lang:pidgin")]
    ])

def onboarding_keyboard() -> InlineKeyboardMarkup:
    """Step 3: The static action button card below the instruction block."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Return to Click Here and Unlock Sanctuary", callback_query_data="unlock")]
    ])

def step4_complete_keyboard() -> InlineKeyboardMarkup:
    """Step 4: The milestone buttons activated only when playback finishes."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Track Playback Complete", callback_query_data="noop")],
        [InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_query_data="confirm_sweep")]
    ])

# ---------------------------------------------------------------------------
# 4. STEP 1 HANDLER — THE FIRST HELLO
# ---------------------------------------------------------------------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # Initialize/Reset the user's session data
    USER_SESSIONS[user_id] = {"to_wipe": []}
    
    welcome_text = f"Welcome, Dear {first_name}! To begin, take the first step. Choose your language version below to enjoy the Sanctuary's Anthem."
    
    await message.answer(text=welcome_text, reply_markup=language_keyboard())

# ---------------------------------------------------------------------------
# 5. STEP 2 HANDLER — LOAD TRACK & LYRICS
# ---------------------------------------------------------------------------
@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    user_id = cb.from_user.id
    
    session = USER_SESSIONS.get(user_id)
    if not session:
        await cb.answer("Please type /start to reset your session.", show_alert=True)
        return
        
    await cb.answer()
    cfg = CONFIGS[lang]

    session["lang"] = lang
    session["duration"] = cfg["duration"]
    session["start_time"] = time.monotonic() 
    session["completed"] = False

    # Dispatch audio asset tracking
    try:
        audio_msg = await bot.copy_message(
            chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"]
        )
        session["to_wipe"].append(audio_msg.message_id)
    except Exception as e:
        log.error("Audio payload connection failed: %s", e)
        await cb.message.answer("⚠️ Could not load track audio. Using simulated mode for testing.")
        # We continue for testing even if the file copy fails due to a mock channel ID

    # Dispatch structural lyrics card
    lyrics_text = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    lyrics_msg = await cb.message.answer(text=lyrics_text, parse_mode=ParseMode.MARKDOWN_V2)
    session["to_wipe"].append(lyrics_msg.message_id)

    # Injecting the dynamic track duration straight into the static guideline card
    instructions_text = (
        f"1️⃣ First, Click Play Button ▶️ Above to Listen Fully \\[{cfg['duration']}s\\]\n\n"
        f"2️⃣ 🔒 Then, Return to Click Here and Unlock Sanctuary"
    )

    # Dispatch instructions card
    instructions_msg = await cb.message.answer(
        text=instructions_text, 
        reply_markup=onboarding_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    session["instructions_msg_id"] = instructions_msg.message_id
    session["to_wipe"].append(instructions_msg.message_id)

# ---------------------------------------------------------------------------
# 6. STEP 3 — THE SMART SHOULDER-TAP GATEKEEPER
# ---------------------------------------------------------------------------
@dp.callback_query(F.data == "unlock")
async def on_unlock(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)

    if not session or session.get("lang") is None:
        await cb.answer("Session expired. Please use /start to initialize.", show_alert=True)
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
        log.error("Failed to transition interface down to Step 4 layout: %s", e)

# ---------------------------------------------------------------------------
# 7. ENGINE BOOTSTRAPPER
# ---------------------------------------------------------------------------
async def main():
    await start_dummy_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
