import os
import re
import time
import math
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, ErrorEvent, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiohttp import web

import db
import portal
import terms

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("repellano")

# --- ENVIRONMENT CONFIGURATIONS ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@RDSTracks")
# Telegram IDs allowed to use /resetme for testing (comma separated, set on Render as ADMIN_IDS)
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}

# --- DEVELOPMENT TESTING OVERRIDE ---
# Durations have been set to 3 seconds so you can instantly verify your Immaculate Clean Sweep.
CONFIGS = {
    "en": {"msg_id": 6, "duration": 3, "title": "English"},    
    "pidgin": {"msg_id": 15, "duration": 3, "title": "Pidgin"},  
}

# --- TEXT BLOCKS (MarkdownV2 unless stated) ---
GREETING = (
    r"Welcome, Dear *{name}*\!" "\n\n"
    r"To begin, take the first step\. Choose your language version "
    r"below to enjoy the Sanctuary's Anthem\."
)

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

INSTRUCTIONS = (
    r"💡 *Optional Tip:* If you wish to replay the Anthem anytime, tap the ➦ arrow beside the track "
    r"playback button on top of the lyrics, then choose *Saved Messages*\." "\n\n"
    r"👇 *Follow the two steps below*"
)

PHASE2_TEXT = r"🏛 *Phase 2: Brief Introduction to Repellano Nigeria Limited \(RNL\)*"

USER_SESSIONS: dict[int, dict] = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

_MD2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def md2_escape(text: str) -> str:
    """Escape user-supplied text (e.g. first names) for MarkdownV2."""
    return _MD2_SPECIAL.sub(r"\\\1", text)


# --- HIGH-PRECISION SECURE TIMING ---
def secs_left(session: dict) -> int:
    end = session.get("end_time", 0.0)
    if not end:
        return 0
    return max(0, math.ceil(end - time.monotonic()))


# --- KEYBOARDS ---
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version", callback_data="lang:pidgin")],
    ])


def listening_keyboard(duration: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"1️⃣ First, click the Play button ▶️ above to listen fully · {duration}s",
            callback_data="noop")],
        [InlineKeyboardButton(
            text="🔒 Then, return to click here and Unlock Sanctuary",
            callback_data="unlock")],
    ])


def complete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Track Playback Complete", callback_data="noop")],
        [InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_data="confirm")],
    ])


# --- HELPERS ---
def new_session() -> dict:
    return {
        "phase": "greeting",
        "lang": None,
        "to_wipe": [],
        "end_time": 0.0,
        "control_msg": None,
        "task": None,
    }


async def delete_messages_safe(chat_id: int, ids: list[int]) -> None:
    """Delete message ids from one user's chat only. Never raises."""
    ids = sorted(set(ids))
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        try:
            await bot.delete_messages(chat_id=chat_id, message_ids=chunk)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.delete_messages(chat_id=chat_id, message_ids=chunk)
            except Exception as e2:
                log.warning("Bulk delete retry failed for %s: %s", chat_id, e2)
        except Exception:
            # Fallback: delete one by one (older aiogram / odd message states)
            for mid in chunk:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=mid)
                except Exception:
                    pass


async def wipe_chat(user_id: int, session: dict) -> None:
    """Cancel any pending timer and wipe every tracked message for this user."""
    task = session.get("task")
    if task and not task.done() and task is not asyncio.current_task():
        task.cancel()
    session["task"] = None
    ids = session["to_wipe"]
    session["to_wipe"] = []
    if ids:
        await delete_messages_safe(user_id, ids)


# --- TOTAL CLEAN SWEEP ---
SWEEP_LOOKBACK = 500  


async def sweep_range(chat_id: int, low: int, high: int) -> None:
    """Delete every message id from low to high in ONE member's chat. Never raises."""
    low = max(1, low)
    if high < low or not hasattr(bot, "delete_messages"):
        return
    ids = list(range(low, high + 1))
    chunks = [ids[i:i + 100] for i in range(0, len(ids), 100)]
    for chunk in reversed(chunks):  # newest first
        for _ in range(2):
            try:
                await bot.delete_messages(chat_id=chat_id, message_ids=chunk)
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                log.warning("Range delete failed for %s (%s-%s): %s", chat_id, chunk[0], chunk[-1], e)
                break
        await asyncio.sleep(0.05)


async def total_sweep(user_id: int, session: dict) -> None:
    """Immaculate clean sweep for one member: remembered messages plus every leftover."""
    task = session.get("task")
    if task and not task.done() and task is not asyncio.current_task():
        task.cancel()
    session["task"] = None
    tracked = [i for i in session["to_wipe"] if i]
    session["to_wipe"] = []

    high = max(tracked or)
    marker_id = None
    try:
        marker = await bot.send_message(chat_id=user_id, text="🧹", parse_mode=None)
        marker_id = marker.message_id
        high = max(high, marker_id)
    except Exception as e:
        log.warning("Sweep marker failed for %s: %s", user_id, e)

    run_low = min(tracked) if tracked else max(1, high - 50)
    await sweep_range(user_id, run_low - SWEEP_LOOKBACK, high)
    await delete_messages_safe(user_id, tracked + ([marker_id] if marker_id else []))

