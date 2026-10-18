# bot.py
# Corrected Production Script for Repellano Onboarding Flow - Render Free Tier

"""
Repellano "Anthem Onboarding Flow" — Telegram bot (aiogram 3.x)
Requires: pip install aiogram aiohttp
Env vars: BOT_TOKEN, CHANNEL_ID (Optional), PORT (Optional)
"""

import asyncio
import os
import logging
import time
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp import web

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("repellano")

# --- CONFIGURATION & ENV VARIABLES ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    BOT_TOKEN = "8642428323:AAHO71GubQl4kvAIeT1dpI_NA2gsqKGS8eI"

CHANNEL_ID = os.getenv("CHANNEL_ID", "@RDSTracks")

# UI update rhythm to protect your account against Telegram FloodWait bans.
TICK = 5 

CONFIGS = {
    "en":     {"msg_id": 6,  "duration": 240, "title": "English"},
    "pidgin": {"msg_id": 15, "duration": 234, "title": "Pidgin"},
}

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
    "<b>[Verse 1]</b>\nThe world market dey spin anyhow, e no dey stop\nForex trading sharp well-well, things just dey pop\nBut inside this Sanctuary, the vision clear pass glass\nWe dey commot the confusion, make the fear join pass\nWe dey change heavy lodu simple tool for everybody.\n\n"
    "<b>[Chorus]</b>\nE simple. E dey run on own. E dey for everyone.\nThirty-five FSSOs, the tech don change the run!\nPower dey for everybody, no matter where you start from\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\nEvery single heart\n\n"
    "<b>[Verse 2]</b>\nThe whole setup dey here to change how things suppose to be\nWhere math and market jam, things arrange properly\nThe system solid well-well, e smooth and e deep\nE dey work sharp-sharp inside silence when the world dey sleep.\n\n"
    "<b>[Verse 3]</b>\nThirty-five FSSOs stand gidigba, everything set well\nFinancial Support Service Offerings, na him we call FSSOs\nAutomated tools wey no dey tire or lose face\nTo support everybody wey dey struggle hard to find small money\n\n"
    "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nFinancial power for you, no matter where you start\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\n\n"
    "<b>[Outro]</b>\nThe Digital Sanctuary.\nWe don build, we don automate, we wan rise.\n[Fade Out][End]"
)

# Corrected layout phrase matching your exact step-by-step documentation rules
GREETING = (
    "Welcome, Dear <b>{name}</b>!\n\n"
    "To begin, take the first step. Choose your language version "
    "below to enjoy the Sanctuary's Anthem."
)

INSTRUCTIONS = (
    "1️⃣ First, click the <b>Play button ▶️ above</b> to listen fully.\n\n"
    "🔒 Then, return here and click <b>Unlock Sanctuary</b> below."
)

PHASE2_TEXT = (
    "✅ <b>Welcome to the Sanctuary.</b>\n\n"
    "📖 <b>Phase 2: Brief Introduction to Repellano Nigeria Limited (RNL)</b>\n\n"
    "Repellano Nigeria Limited (RNL) is established to drive innovations, "
    "secure local development opportunities, and provide structural excellence "
    "across all related domains. Welcome aboard your onboarding journey!\n"
)

# --- ISOLATED SESSION CONFIGURATION (Step 5 Multi-user isolation) ---
USER_SESSIONS: dict[int, dict] = {}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- SECURITY HANDLERS ---
async def safe_delete(chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        log.debug("Delete failed safely for msg %s: %s", message_id, e)

async def safe_edit(chat_id: int, message_id: int, text: str, markup) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                                    text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                                        text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
        except Exception:
            pass
    except Exception as e:
        log.debug("Edit skipped safely: %s", e)

def track(session: dict, message_id: int) -> None:
    if message_id not in session["to_wipe"]:
        session["to_wipe"].append(message_id)

# --- KEYBOARD MARKUPS ---
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version",  callback_data="lang:pidgin")],
    ])

def listening_keyboard(lang: str, remaining: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"▶️ Now Playing — {remaining}s remaining", callback_data="noop")],
        [InlineKeyboardButton(text=f"🔒 Unlock Sanctuary ({remaining}s)", callback_data="unlock")],
    ])

def done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Track Playback Complete", callback_data="noop")],
        [InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_data="confirm")],
    ])

# --- BACKGROUND COUNTDOWN ENGINE ---
async def run_countdown(user_id: int, lang: str, message_id: int, duration: int) -> None:
    start_time = time.time()
    end_time = start_time + duration
    cfg = CONFIGS[lang]

    while True:
        await asyncio.sleep(TICK)
        session = USER_SESSIONS.get(user_id)
        if not session or session.get("task") != asyncio.current_task():
            break

        now = time.time()
        remaining = int(max(0, end_time - now))
        session["remaining"] = remaining

        if remaining <= 0:
            await safe_edit(
                chat_id=user_id,
                message_id=message_id,
                text=f"✅ <b>{cfg['title']} Anthem Finished!</b>\nPlease tap below to confirm listening.",
                markup=done_keyboard()
            )
            break
        else:
            await safe_edit(
                chat_id=user_id,
                message_id=message_id,
                text=f"⏳ <b>{cfg['title']} Anthem</b> — {remaining} seconds remaining.",
                markup=listening_keyboard(lang, remaining)
            )

# --- TELEGRAM INBOUND TRIGGERS ---
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    name = message.from_user.first_name or "Leno"

    # Pristine Wipe if user restarts the process unexpectedly mid-way
    old = USER_SESSIONS.pop(user_id, None)
    if old:
        if old.get("task") and not old["task"].done():
            old["task"].cancel()
        for mid in old.get("to_wipe", []):
            await safe_delete(user_id, mid)

    session = {"lang": None, "to_wipe": [], "task": None, "remaining": 0, "control_id": None, "end_time": 0}
    USER_SESSIONS[user_id] = session

    # Fixed: Force parse_mode="HTML" explicitly inside the method call to fix name formatting bug
    greeting = await message.answer(
        GREETING.format(name=name), 
        reply_markup=lang_keyboard(),
        parse_mode=ParseMode.HTML
    )
    track(session, greeting.message_id)

@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    if lang not in CONFIGS:
        await cb.answer("Unknown language option chosen.", show_alert=True)
        return

    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)
    if session is None:
        await cb.answer("Please re-run /start to setup session parameters.", show_alert=True)
        return

    await cb.answer()
    cfg = CONFIGS[lang]
    session["lang"] = lang

