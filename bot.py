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
import phase2
import portal

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("repellano")

# --- ENVIRONMENT CONFIGURATIONS ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@RDSTracks")
# Telegram IDs allowed to use /resetme for testing (comma separated, set on Render as ADMIN_IDS)
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}

CONFIGS = {
    "en": {"msg_id": 6, "duration": 250, "title": "English"},    # 240s song + 10s
    "pidgin": {"msg_id": 15, "duration": 244, "title": "Pidgin"},  # 234s song + 10s
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

# The two instruction lines now live on the buttons, so the message body stays short.
INSTRUCTIONS = (
    r"💡 *Optional Tip:* If you wish to replay the Anthem anytime, tap the ➦ arrow beside the track "
    r"playback button on top of the lyrics, then choose *Saved Messages*\." "\n\n"
    r"👇 *Follow the two steps below*"
)

PHASE2_TEXT = r"🏛 *Phase 2: Brief Introduction to Repellano Nigeria Limited \(RNL\)*"

# --- STATE ---
# phase: greeting -> loading -> listening -> complete -> confirming -> done
USER_SESSIONS: dict[int, dict] = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()
phase2.init(USER_SESSIONS)
dp.include_router(phase2.router)

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
# The bot used to delete only the message ids it remembered. A restart, a glitch or a poor
# network could make it forget some, and those were left behind. The sweep below also deletes
# by ID RANGE, so anything in this member's chat inside the range goes, remembered or not.
# Telegram simply skips ids that do not exist, so this is safe to run over a wide range.
SWEEP_LOOKBACK = 500  # how many ids below this run's first message to check for leftovers


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

    # A tiny marker message tells us the newest message id in this chat right now.
    high = max(tracked or [0])
    marker_id = None
    try:
        marker = await bot.send_message(chat_id=user_id, text="🧹", parse_mode=None)
        marker_id = marker.message_id
        high = max(high, marker_id)
    except Exception as e:
        log.warning("Sweep marker failed for %s: %s", user_id, e)

    run_low = min(tracked) if tracked else max(1, high - 50)
    await sweep_range(user_id, run_low - SWEEP_LOOKBACK, high)
    # Belt and braces: also delete the remembered ids directly (works on any aiogram version)
    await delete_messages_safe(user_id, tracked + ([marker_id] if marker_id else []))

    async def second_pass() -> None:
        await asyncio.sleep(3)  # catches anything that arrived late or failed the first time
        await sweep_range(user_id, run_low, high)  # never above the marker: the next step's message is newer

    asyncio.create_task(second_pass())
    log.info("Total sweep done for user %s (ids %s-%s)", user_id, run_low - SWEEP_LOOKBACK, high)


async def show_complete(user_id: int, session: dict) -> None:
    """Morph the control buttons into the 'playback complete' state (single API call)."""
    if session.get("phase") not in ("listening", "complete"):
        return
    session["phase"] = "complete"
    msg_id = session.get("control_msg")
    if not msg_id:
        return
    for attempt in range(2):
        try:
            await bot.edit_message_reply_markup(
                chat_id=user_id, message_id=msg_id, reply_markup=complete_keyboard()
            )
            log.info("Buttons morphed for user %s", user_id)
            return
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramBadRequest as e:
            # "message is not modified" or message already deleted: nothing more to do
            log.info("Keyboard edit skipped for %s: %s", user_id, e)
            return
        except Exception as e:
            log.warning("Keyboard edit failed for %s (attempt %s): %s", user_id, attempt + 1, e)
            await asyncio.sleep(2)


async def complete_after(user_id: int, session: dict) -> None:
    """One sleeping task per user: no polling, no repeated edits, one API call when done."""
    try:
        while True:
            remaining = session["end_time"] - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(remaining + 0.05)
        if USER_SESSIONS.get(user_id) is not session:
            return
        await show_complete(user_id, session)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("complete_after crashed for %s", user_id)


# --- STEP 1: /start ---
async def wipe_old_quietly(user_id: int, old: dict | None, greeting_id: int) -> None:
    """Clean up the previous run in the background so it can never block the greeting.
    Even with no memory of an old run (e.g. after a restart), leftovers below the new
    greeting are swept away so every restart starts on a clean screen."""
    try:
        if old:
            await wipe_chat(user_id, old)
        await sweep_range(user_id, greeting_id - SWEEP_LOOKBACK, greeting_id - 1)
    except Exception:
        log.exception("Background wipe failed for %s", user_id)


async def begin_flow(user_id: int, name: str, trigger_msg_id: int | None) -> None:
    """Start (or fully restart) the onboarding loop for one user."""
    old = USER_SESSIONS.get(user_id)
    session = new_session()
    USER_SESSIONS[user_id] = session
    if trigger_msg_id:
        session["to_wipe"].append(trigger_msg_id)

    # Greeting goes out FIRST, before any cleanup, so it always appears
    greeting = await bot.send_message(
        chat_id=user_id,
        text=GREETING.format(name=md2_escape(name)),
        reply_markup=lang_keyboard(),
    )
    session["to_wipe"].append(greeting.message_id)

    asyncio.create_task(wipe_old_quietly(user_id, old, greeting.message_id))
    asyncio.create_task(db.safe(db.upsert_member(user_id, name)))


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    log.info("/start received from %s", user_id)
    await begin_flow(user_id, message.from_user.first_name or "Leno", message.message_id)


@dp.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Your Telegram ID: {message.from_user.id}", parse_mode=None)


@dp.message(Command("resetme"))
async def cmd_resetme(message: Message) -> None:
    """Testing helper: wipes the tester's saved progress and restarts the whole flow."""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    await db.safe(db.reset_member(user_id))
    await begin_flow(user_id, message.from_user.first_name or "Leno", message.message_id)


# --- STEP 2: LOAD SONG & LYRICS ---
@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    user_id = cb.from_user.id
    cfg = CONFIGS.get(lang)
    session = USER_SESSIONS.get(user_id)

    if cfg is None:
        await cb.answer()
        return

    # Self-heal: if the bot was restarted, the old greeting buttons still work
    if session is None:
        session = new_session()
        USER_SESSIONS[user_id] = session
        if cb.message:
            session["to_wipe"].append(cb.message.message_id)

    # Ignore double taps / taps while already loading or listening
    if session["phase"] != "greeting":
        await cb.answer()
        return
    session["phase"] = "loading"
    await cb.answer()

    session["lang"] = lang

    # 1. Audio track
    try:
        audio_msg = await bot.copy_message(
            chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"]
        )
        session["to_wipe"].append(audio_msg.message_id)
    except Exception as e:
        log.error("Audio copy failed: %s", e)
        err = await bot.send_message(
            chat_id=user_id,
            text="⚠️ Could not load track audio. Please try again.",
            parse_mode=None,
        )
        session["to_wipe"].append(err.message_id)
        session["phase"] = "greeting"
        return

    # Reference clock starts the moment the track is in the user's chat
    session["end_time"] = time.monotonic() + cfg["duration"]

    # 2. Lyrics
    lyrics_text = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    lyrics_msg = await bot.send_message(chat_id=user_id, text=lyrics_text, parse_mode=ParseMode.HTML)
    session["to_wipe"].append(lyrics_msg.message_id)

    # 3. Control message (instructions live on the buttons, duration on the first one)
    control = await bot.send_message(
        chat_id=user_id, text=INSTRUCTIONS, reply_markup=listening_keyboard(cfg["duration"])
    )
    session["to_wipe"].append(control.message_id)
    session["control_msg"] = control.message_id
    session["phase"] = "listening"

    # User restarted mid-load: clean up what we just sent
    if USER_SESSIONS.get(user_id) is not session:
        await wipe_chat(user_id, session)
        return

    # One lightweight sleeping task per user (a single edit when the song ends)
    session["task"] = asyncio.create_task(complete_after(user_id, session))
    log.info("Timer started for user %s: %ss (%s)", user_id, cfg["duration"], lang)


@dp.callback_query(F.data == "noop")
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer()


# --- STEP 3: ON-DEMAND ANTI-CHEAT GATEKEEPER ---
@dp.callback_query(F.data == "unlock")
async def on_unlock(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)

    if not session or session.get("phase") not in ("listening", "complete"):
        await cb.answer("Session expired. Please execute /start to begin.", show_alert=True)
        return

    remaining = secs_left(session)
    if remaining > 0:
        await cb.answer(
            f"🔒 Please listen fully to unlock the Sanctuary.\n"
            f"⏳ ({remaining} seconds remaining).",
            show_alert=True,
        )
    else:
        # Time is up but the timer task hasn't morphed the buttons yet: do it now
        await cb.answer()
        await show_complete(user_id, session)


# --- STEP 4: THE IMMACULATE CLEAN SWEEP ---
@dp.callback_query(F.data == "confirm")
async def on_confirm(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)

    if not session or session.get("phase") not in ("listening", "complete"):
        await cb.answer("Session expired. Please execute /start to begin.", show_alert=True)
        return

    # Server-side check: never trust the button alone
    remaining = secs_left(session)
    if remaining > 0:
        await cb.answer(
            f"🔒 Please listen fully to unlock the Sanctuary.\n"
            f"⏳ ({remaining} seconds remaining).",
            show_alert=True,
        )
        return

    session["phase"] = "confirming"  # blocks double taps
    await cb.answer()
    asyncio.create_task(db.safe(db.record_anthem_complete(user_id, session.get("lang"))))

    # Wipe audio, lyrics, control message, greeting and the user's /start (this user only)
    await total_sweep(user_id, session)

    # Fresh slate: print Phase 2
    await portal.handoff(bot, user_id, session, lambda: USER_SESSIONS.get(user_id) is session)


# --- FALLBACKS ---
@dp.message()
async def any_other_message(message: Message) -> None:
    """If a user with no active session writes anything, start the flow for them."""
    user_id = message.from_user.id
    session = USER_SESSIONS.get(user_id)
    if session is None or session.get("phase") == "done":
        log.info("Message from %s with no active session: starting flow", user_id)
        await begin_flow(user_id, message.from_user.first_name or "Leno", message.message_id)


@dp.error()
async def on_error(event: ErrorEvent) -> bool:
    log.error("Unhandled error: %s", event.exception, exc_info=event.exception)
    return True


# --- WEB FRAMEWORK STATUS PORTS ---
async def health_handler(request):
    return web.Response(text="Server Online.")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/portal", portal.portal_page)
    app.router.add_get("/api/progress", portal.api_get_progress)
    app.router.add_post("/api/progress/read", portal.api_mark_read)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info(f"Web server running on port {port}")


async def start_bot_polling():
    log.info("Launching bot polling engine...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


async def main():
    await db.init()
    await asyncio.gather(
        start_web_server(),
        start_bot_polling(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
