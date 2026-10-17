"""
Repellano "Anthem Onboarding Flow" — Telegram bot (aiogram 3.x)
Requires:  pip install aiogram aiohttp
Env vars:  BOT_TOKEN = "8642428323:AAHO71GubQl4kvAIeT1dpI_NA2gsqKGS8eI"
"""
import asyncio, os, logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp import web

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("repellano")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN empty. Set it in Render -> Environment.")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@RDSTracks")

# 1 = smooth but ~240 API edits/user (FloodWait risk). 3 = recommended.
TICK = 1

CONFIGS = {
    "en":     {"msg_id": 6,  "duration": 240, "title": "English"},
    "pidgin": {"msg_id": 15, "duration": 234, "title": "Pidgin"},
}

LYRICS = {
    "en": (
        "🎵 *REPELLANO — THE SANCTUARY ANTHEM (English)*\n"
        "____________________________________\n\n"
        "[Verse 1]\n<paste English lyrics>\n\n"
        "[Chorus]\n<paste English lyrics>\n\n"
        "[Verse 2]\n<paste English lyrics>\n\n"
        "[Outro]\n<paste English lyrics>\n"
        "____________________________________\n"
    ),
    "pidgin": (
        "🎵 *REPELLANO — THE SANCTUARY ANTHEM (Pidgin)*\n"
        "____________________________________\n\n"
        "[Verse 1]\n<paste Pidgin lyrics>\n\n"
        "[Chorus]\n<paste Pidgin lyrics>\n\n"
        "[Verse 2]\n<paste Pidgin lyrics>\n\n"
        "[Outro]\n<paste Pidgin lyrics>\n"
        "____________________________________\n"
    ),
}

INSTRUCTIONS = (
    "1️⃣  First, click the *Play button ▶️ above* to listen fully.\n\n"
    "🔒  Then, return here and click *Unlock Sanctuary* below."
)

PHASE2_TEXT = (
    "✅ *Welcome to the Sanctuary.*\n\n"
    "📖 *Phase 2: Brief Introduction to Repellano Nigeria Limited (RNL)*\n\n"
    "<paste your RNL introduction here>\n"
)

USER_SESSIONS: dict[int, dict] = {}   # user_id -> session (RAM only)

bot = Bot(token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()
# ---- SAFE HELPERS (one failure never kills the flow) ----
async def safe_delete(chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest as e:
        log.debug("delete skipped (%s,%s): %s", chat_id, message_id, e)
    except Exception as e:
        log.warning("delete failed (%s,%s): %s", chat_id, message_id, e)

async def safe_edit(chat_id: int, message_id: int, text: str, markup) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
            text=text, reply_markup=markup)
    except TelegramRetryAfter as e:
        log.warning("FloodWait %ss -> backoff", e.retry_after)
        await asyncio.sleep(e.retry_after)
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                text=text, reply_markup=markup)
        except Exception as e2:
            log.debug("edit retry failed: %s", e2)
    except TelegramBadRequest as e:
        if "not modified" not in str(e).lower():
            log.debug("edit skipped: %s", e)
    except Exception as e:
        log.warning("edit failed: %s", e)

def track(session: dict, message: Message) -> None:
    session["to_wipe"].append(message.message_id)

# ---- KEYBOARDS ----
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version",  callback_data="lang:pidgin")],
    ])

def listening_keyboard(lang: str, remaining: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"▶️ Now Playing — {remaining}s remaining", callback_data="noop")],
        [InlineKeyboardButton(
            text=f"🔒 Unlock Sanctuary ({remaining}s)", callback_data="unlock")],
    ])

def done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Track Playback Complete", callback_data="noop")],
        [InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_data="confirm")],
    ])
# ⚠️ CHANGE in Part 1: use HTML, not MARKDOWN, because lyrics use <b> tags
# bot = Bot(token=BOT_TOKEN,
#     default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# ⚠️ CHANGE in Part 1: greetings must use HTML tags now:
GREETING = ("Welcome, <b>{name}!</b>\n\n"
    "To begin, take the first step. Choose your language version "
    "below to enjoy the Sanctuary's Anthem.")

INSTRUCTIONS = (
    "1️⃣  First, click the <b>Play button ▶️ above</b> to listen fully.\n\n"
    "🔒  Then, return here and click <b>Unlock Sanctuary</b> below."
)

PHASE2_TEXT = (
    "✅ <b>Welcome to the Sanctuary.</b>\n\n"
    "📖 <b>Phase 2: Brief Introduction to Repellano Nigeria Limited (RNL)</b>\n\n"
    "<paste your RNL introduction here>\n"
)

# ---- /start ----
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    name = message.from_user.first_name or "Friend"

    old = USER_SESSIONS.pop(user_id, None)
    if old and old.get("task"):
        old["task"].cancel()

    session = {"lang": None, "to_wipe": [], "task": None, "remaining": 0}
    USER_SESSIONS[user_id] = session

    greeting = await message.answer(
        GREETING.format(name=name), reply_markup=lang_keyboard())
    track(session, greeting)

# ---- LANGUAGE PICK ----
@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    if lang not in CONFIGS:
        await cb.answer("Unknown language.", show_alert=True)
        return

    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)
    if session is None:
        session = {"lang": None, "to_wipe": [], "task": None, "remaining": 0}
        USER_SESSIONS[user_id] = session

    await cb.answer()
    cfg = CONFIGS[lang]
    session["lang"] = lang

    # 1) Audio track copied from the channel
    try:
        audio_msg = await bot.copy_message(
            chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"])
        track(session, audio_msg)
    except Exception as e:
        log.error("copy_message failed: %s", e)
        await cb.message.answer(
            "⚠️ Could not load the audio track. Please try again shortly.")
        return

    # 2) Lyrics card (EN or Pidgin, HTML)
    lyrics = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    track(session, await cb.message.answer(lyrics))

    # 3) Instruction blocks
    track(session, await cb.message.answer(INSTRUCTIONS))

    # 4) Live control message with the two stacked buttons
    dur = cfg["duration"]
    session["remaining"] = dur
    control = await cb.message.answer(
        f"⏳ <b>{cfg['title']} Anthem</b> — {dur} seconds",
        reply_markup=listening_keyboard(lang, dur))
    track(session, control)
    session["control_id"] = control.message_id

    # 5) Independent countdown task per user
    session["task"] = asyncio.create_task(
        run_countdown(user_id, lang, control.message_id, dur))
# ---- EARLY "UNLOCK" CLICK -> gentle popup ----
@dp.callback_query(F.data == "unlock")
async def on_unlock(cb: CallbackQuery) -> None:
    session = USER_SESSIONS.get(cb.from_user.id)
    if not session:
        await cb.answer("Please send /start to begin.", show_alert=True)
        return
    remaining = session.get("remaining", 0)
    if remaining > 0:
        await cb.answer(
            f"🔒 Please listen fully to unlock the Sanctuary. "
            f"({remaining} seconds remaining).", show_alert=True)
    else:
        await cb.answer("Playback complete — tap Confirm.", show_alert=True)

# ---- CONFIRM -> silent wipe -> Phase 2 ----
@dp.callback_query(F.data == "confirm")
async def on_confirm(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)
    if not session:
        await cb.answer("Please send /start to begin.", show_alert=True)
        return
    if session.get("remaining", 0) > 0:
        await cb.answer(
            f"🔒 Please listen fully to unlock the Sanctuary. "
            f"({session['remaining']} seconds remaining).", show_alert=True)
        return

    await cb.answer("Unlocking the Sanctuary…")

    task = session.get("task")
    if task and not task.done():
        task.cancel()

    # SILENT BACKGROUND WIPE — bot's own messages, THIS user only
    for mid in session.get("to_wipe", []):
        await safe_delete(user_id, mid)
        await asyncio.sleep(0.05)
    session["to_wipe"].clear()

    # Clean slate -> Phase 2
    await bot.send_message(user_id, PHASE2_TEXT)
    USER_SESSIONS.pop(user_id, None)

# ---- NOOP (top, non-interactive button) ----
@dp.callback_query(F.data == "noop")
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer()

# ---- HEALTH SERVER (Render free tier needs an open port) ----
async def health(_: web.Request) -> web.Response:
    return web.Response(text="Repellano bot is alive.")

async def start_web() -> None:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Health server on :%s", port)

# ---- MAIN ----
async def main() -> None:
    await start_web()
    log.info("Bot starting… polling.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped.")
