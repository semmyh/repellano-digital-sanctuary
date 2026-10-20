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
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # Replace with your actual bot token between quotes
bot = Bot(token=TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# --- MILESTONE PERMANENT ASSETS (Locked-In Project Configuration) ---
CONFIGS = {
    "en": {"duration": 240, "msg_id": 123},       # Track file reference for English
    "pidgin": {"duration": 180, "msg_id": 124}    # Track file reference for Pidgin
}

CHANNEL_ID = -1001234567890  # Your physical Telegram track repository channel ID
USER_SESSIONS = {} 

EN_LYRICS = (
    "<b>📜 Repellano Anthem (English Lyrics)</b>\n\n"
    "<b>[Intro]</b>\nWelcome to the Sanctuary.\nWhere the chaotic markets find their perfect peace.\nThis is SemLeno's Repellano Digital Sanctuary.\n\n"
    "<b>[Verse 1]</b>\nThe global markets spin in a wild, endless race\nComplex forex trading moving at a blinding pace\nBut inside the Sanctuary, the vision is crystal clear\nWe strip away the chaos, we break down the fear\nTurning heavy burdens into a simple tool for all.\n\n"
    "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nUniversal empowerment, no matter where you start\nRepellano lifting up, up, up, up, every single heart!\nEvery single heart!\nEvery single heart\n\n"
    "<b>[Verse 2]</b>\nAn ecosystem built to redefine the grand design\nWhere mathematics meets the market, aligning line by line\nA seamless architecture, steady, smooth, and deep\nWorking in the silence while the world is fast asleep.\n\n"
    "<b>[Verse 3]</b>\nThirty-five FSSOs standing structured and strong\nFinancial Support Service Offerings where they belong\nAutomated utilities that never tire or fade\nTo help all those struggling with their finances\n\n"
    "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nUniversal empowerment, no matter where you start\nRepellano lifting up, up, up, up, every single heart!\nEvery single heart!\nEvery single heart!\n\n"
    "<b>[Outro]</b>\nThe Digital Sanctuary.\nWe build, we automate, we rise.\n[Fade Out] [End]"
)

PIDGIN_LYRICS = (
    "<b>📜 Repellano Anthem (Pidgin Lyrics)</b>\n\n"
    "<b>[Intro]</b>\nWelcome to the Sanctuary.\nWhere jaga jaga forex markets find their perfect peace.\nThis na Semleno Repellano Digital Sanctuary.\n\n"
    "<b>[Verse 1]</b>\nThe world market dey spin anyhow, e no dey stop\nForex trading sharp well-well, things just dey pop\nBut inside this Sanctuary, the vision clear pass glass\nWe dey commot the confusion, make the fear join pass\nWe dey change heavy load to simple tool for everybody.\n\n"
    "<b>[Chorus]</b>\nE simple. E dey run on own. E dey for everyone.\nThirty-five FSSOs, the tech don change the run!\nPower dey for everybody, no matter where you start from\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\nEvery single heart\n\n"
    "<b>[Verse 2]</b>\nThe whole setup dey here to change how things suppose to be\nWhere math and market jam, things arrange properly\nThe system solid well-well, e smooth and e deep\nE dey work sharp-sharp inside silence when the world dey sleep.\n\n"
    "<b>[Verse 3]</b>\nThirty-five FSSOs stand gidigba, everything set well\nFinancial Support Service Offerings, na him we call FSSOs\nAutomated tools wey no dey tire or lose face\nTo support everybody wey dey struggle hard to find small money\n\n"
    "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nFinancial power for you, no matter where you start\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\n\n"
    "<b>[Outro]</b>\nThe Digital Sanctuary.\nWe don build, we don automate, we wan rise.\n[Fade Out][End]"
)

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
# 3. INTERFACE BUILDERS (Permanent UI Layouts)
# ---------------------------------------------------------------------------
def language_keyboard() -> InlineKeyboardMarkup:
    """Step 1 Milestone: Two clean, stacked language selection buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_query_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version", callback_query_data="lang:pidgin")]
    ])

def onboarding_keyboard() -> InlineKeyboardMarkup:
    """Step 3 Milestone: Static action button card with zero running timers."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Return to Click Here and Unlock Sanctuary", callback_query_data="unlock")]
    ])

def step4_complete_keyboard() -> InlineKeyboardMarkup:
    """Step 4 Foundation: Milestone confirmation elements."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Track Playback Complete", callback_query_data="noop")],
        [InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_query_data="confirm_sweep")]
    ])

# ---------------------------------------------------------------------------
# 4. STEP 1 PROGRESSIVE IMPLEMENTATION — THE FIRST HELLO
# ---------------------------------------------------------------------------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # Securely reset tracking matrix
    USER_SESSIONS[user_id] = {"to_wipe": []}
    
    welcome_text = f"Welcome, Dear {first_name}! To begin, take the first step. Choose your language version below to enjoy the Sanctuary's Anthem."
    await message.answer(text=welcome_text, reply_markup=language_keyboard())

# ---------------------------------------------------------------------------
# 5. STEP 2 PROGRESSIVE IMPLEMENTATION — LOAD TRACK & LYRICS
# ---------------------------------------------------------------------------
@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    # FIXED PERMANENTLY: Fixed string indexing syntax to solve freeze bug
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

    # 1. Fetch and copy Audio Track from hosting channel
    try:
        audio_msg = await bot.copy_message(
            chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"]
        )
        session["to_wipe"].append(audio_msg.message_id)
    except Exception as e:
        log.error("Audio connection skipped for mock asset validation: %s", e)
        await cb.message.answer("⚠️ <i>[Audio Track Node Loaded — Verify physical Channel ID config to load actual file]</i>", parse_mode=ParseMode.HTML)

    # 2. Deliver corresponding lyrics text block (Using HTML ParseMode to support your styling)
    lyrics_text = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    lyrics_msg = await cb.message.answer(text=lyrics_text, parse_mode=ParseMode.HTML)
    session["to_wipe"].append(lyrics_msg.message_id)

    # 3. Dynamic layout text compilation
    instructions_text = (
        f"1️⃣ First, Click Play Button ▶️ Above to Listen Fully [{cfg['duration']}s]\n\n"
        f"2️⃣ 🔒 Then, Return to Click Here and Unlock Sanctuary"
    )

    # 4. Deliver Guidelines & Engage Static Lock Structure
    instructions_msg = await cb.message.answer(
        text=instructions_text, 
        reply_markup=onboarding_keyboard(),
        parse_mode=ParseMode.HTML
    )
    session["instructions_msg_id"] = instructions_msg.message_id
    session["to_wipe"].append(instructions_msg.message_id)

# ---------------------------------------------------------------------------
# 6. STEP 3 PROGRESSIVE IMPLEMENTATION — SMART SHOULDER-TAP GATEKEEPER
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

    # High-precision alert handling
    if remaining > 0:
        await cb.answer(
            text=f"🔒 Please listen fully to unlock the Sanctuary.\n"
                 f"⏳ {remaining} second(s) remaining.",
