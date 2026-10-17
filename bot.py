"""
Repellano "Anthem Onboarding Flow" — Telegram bot (aiogram 3.x)
==============================================================
Flow:
  /start  ->  warm greeting + language buttons (EN / Pidgin)
  pick lang -> copies Audio Track from @RDSTracks + full Lyrics card + 2 instruction blocks
  listening -> control message with 2 stacked buttons:
                 TOP:    counts down 240s (EN) / 234s (Pidgin)
                 BOTTOM: "unlock" button -> early click = popup with seconds remaining
  finished -> TOP becomes "Track Playback Complete"
              BOTTOM becomes "Confirm Listening Fully" (green check)
  confirm  -> silently deletes the bot's own onboarding messages for THAT user only,
              then prints Phase 2: Brief Introduction to Repellano Nigeria Limited (RNL)

Honest limits baked into the design (read the notes at the bottom):
  * Telegram has NO "user listened to audio" event. The countdown is an honour lock.
  * A bot can only delete ITS OWN messages, and only within 48h.
  * USER_SESSIONS is RAM-only -> free-tier hosts sleep and lose active timers.
    (Health endpoint + external pinger included to mitigate.)

Requires:  pip install aiogram==3.* aiohttp
Env vars:  BOT_TOKEN, CHANNEL_ID (optional override)
"""

import asyncio
import os
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp import web

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("repellano")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN env var is empty. Set it in Render -> Environment.")

CHANNEL_ID = os.getenv("CHANNEL_ID", "@RDSTracks")

# How often the countdown button is re-edited (seconds).
# 1 = buttery smooth but ~240 API calls per user -> FloodWait risk under load.
# 3 = recommended for real traffic. Bump to 3 if you see retry warnings.
TICK = 1

# message_id of the audio inside CHANNEL_ID for each language.
CONFIGS = {
    "en":     {"msg_id": 6,  "duration": 240, "title": "English"},
    "pidgin": {"msg_id": 15, "duration": 234, "title": "Pidgin"},
}

# ---- Lyrics text cards (fill these with the real lyrics) --------------------
LYRICS = {
    "en": (
        "🎵 *REPELLANO — THE SANCTUARY ANTHEM (English)*\n"
        "____________________________________\n\n"
        "[Verse 1]\n"
        "<paste English lyrics here>\n\n"
        "[Chorus]\n"
        "<paste English lyrics here>\n\n"
        "[Verse 2]\n"
        "<paste English lyrics here>\n\n"
        "[Outro]\n"
        "<paste English lyrics here>\n"
        "____________________________________\n"
    ),
    "pidgin": (
        "🎵 *REPELLANO — THE SANCTUARY ANTHEM (Pidgin)*\n"
        "____________________________________\n\n"
        "[Verse 1]\n"
        "<paste Pidgin lyrics here>\n\n"
        "[Chorus]\n"
        "<paste Pidgin lyrics here>\n\n"
        "[Verse 2]\n"
        "<paste Pidgin lyrics here>\n\n"
        "[Outro]\n"
        "<paste Pidgin lyrics here>\n"
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

# ----------------------------------------------------------------------------
# STATE  (RAM only — see notes)
# ----------------------------------------------------------------------------
USER_SESSIONS: dict[int, dict] = {}   # user_id -> session dict

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()


# ----------------------------------------------------------------------------
# SAFE HELPERS  (never let one failure kill the flow)
# ----------------------------------------------------------------------------
async def safe_delete(chat_id: int, message_id: int) -> None:
    """Delete a message; ignore if already gone / too old / no permission."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest as e:
        log.debug("delete skipped (%s, %s): %s", chat_id, message_id, e)
    except Exception as e:  # noqa: BLE001
        log.warning("delete failed (%s, %s): %s", chat_id, message_id, e)


async def safe_edit(chat_id: int, message_id: int, text: str, markup) -> None:
    """Edit a message, swallowing FloodWait by backing off and retrying once."""
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup
        )
    except TelegramRetryAfter as e:
        log.warning("FloodWait %ss on edit -> backing off", e.retry_after)
        await asyncio.sleep(e.retry_after)
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup
            )
        except Exception as e2:  # noqa: BLE001
            log.debug("edit retry failed: %s", e2)
    except TelegramBadRequest as e:
        # "message is not modified" happens when the text is identical -> fine
        if "not modified" not in str(e).lower():
            log.debug("edit skipped: %s", e)
    except Exception as e:  # noqa: BLE001
        log.warning("edit failed: %s", e)


def track(session: dict, message: Message) -> None:
    """Remember a bot message id so we can wipe it later."""
    session["to_wipe"].append(message.message_id)


# ----------------------------------------------------------------------------
# KEYBOARDS
# ----------------------------------------------------------------------------
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en")],
            [InlineKeyboardButton(text="🎧 Pidgin Version",  callback_data="lang:pidgin")],
        ]
    )


def listening_keyboard(lang: str, remaining: int) -> InlineKeyboardMarkup:
    cfg = CONFIGS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"▶️ Now Playing — {remaining}s remaining",
                callback_data="noop",
            )],
            [InlineKeyboardButton(
                text=f"🔒 Unlock Sanctuary ({remaining}s)",
                callback_data="unlock",
            )],
        ]
    )


def done_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🎧 Track Playback Complete",
                callback_data="noop",
            )],
            [InlineKeyboardButton(
                text="✅ Confirm Listening Fully",
                callback_data="confirm",
            )],
        ]
    )


# ----------------------------------------------------------------------------
# /start
# ----------------------------------------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    name = message.from_user.first_name or "Friend"

    # Fresh slate for this user (handles re-/start cleanly)
    old = USER_SESSIONS.pop(user_id, None)
    if old and old.get("task"):
        old["task"].cancel()

    session = {"lang": None, "to_wipe": [], "task": None, "remaining": 0}
    USER_SESSIONS[user_id] = session

    # Track the /start so we can try to remove it later (bot CANNOT delete the
    # user's own /start message — only our reply). We wipe what we can.
    greeting = await message.answer(
        f"Welcome, *{name}!*\n\n"
        "To begin, take the first step. Choose your language version below "
        "to enjoy the Sanctuary's Anthem.",
        reply_markup=lang_keyboard(),
    )
    track(session, greeting)


# ----------------------------------------------------------------------------
# LANGUAGE PICK
# ----------------------------------------------------------------------------
@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    if lang not in CONFIGS:
        await cb.answer("Unknown language.", show_alert=True)
        return

    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)
    if session is None:
        # User hit an old button after a restart -> rebuild session
        session = {"lang": None, "to_wipe": [], "task": None, "remaining": 0}
        USER_SESSIONS[user_id] = session

    await cb.answer()
    cfg = CONFIGS[lang]
    session["lang"] = lang

    # 1) Audio track — copied from the channel (bot must be able to read it)
    try:
        audio_msg = await bot.copy_message(
            chat_id=user_id,
            from_chat_id=CHANNEL_ID,
            message_id=cfg["msg_id"],
        )
        track(session, audio_msg)
    except Exception as e:  # noqa: BLE001
        log.error("copy_message failed: %s", e)
        await cb.message.answer(
            "⚠️ Could not load the audio track. Please try again in a moment."
        )
        return

    # 2) Full lyrics text card
    lyrics_msg = await cb.message.answer(LYRICS[lang])
    track(session, lyrics_msg)

    # 3) Two stacked instruction blocks
    instr_msg = await cb.message.answer(INSTRUCTIONS)
    track(session, instr_msg)

    # 4) Control message with the two live buttons
    dur = cfg["duration"]
    session["remaining"] = dur
    control = await cb.message.answer(
        f"⏳ *{cfg['title']} Anthem* — {dur} seconds",
        reply_markup=listening_keyboard(lang, dur),
    )
    track(session, control)
    session["control_id"] = control.message_id

    # 5) Kick off the countdown task for THIS user only
    session["task"] = asyncio.create_task(
        run_countdown(user_id, lang, control.message_id, dur)
    )


# ----------------------------------------------------------------------------
# COUNTDOWN  (one independent task per user -> full concurrency)
# ----------------------------------------------------------------------------
async def run_countdown(user_id: int, lang: str, control_id: int, duration: int) -> None:
    session = USER_SESSIONS.get(user_id)
    if session is None:
        return

    remaining = duration
    try:
        while remaining > 0:
            await asyncio.sleep(TICK)
            remaining -= TICK
            if remaining < 0:
                remaining = 0
            session["remaining"] = remaining

            # Re-render only on the last second or every TICK boundary
            if remaining == 0 or remaining % TICK == 0:
                await safe_edit(
                    user_id, control_id,
                    f"⏳ *{CONFIGS[lang]['title']} Anthem* — {remaining} seconds",
                    listening_keyboard(lang, remaining),
                )

        # Finished -> morph both buttons
        session["remaining"] = 0
        await safe_edit(
            user_id, control_id,
            f"🎧 *{CONFIGS[lang]['title']} Anthem* — playback complete.\n\n"
            "Tap below to confirm and enter the Sanctuary.",
            done_keyboard(),
        )
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("countdown error for %s: %s", user_id, e)


# ----------------------------------------------------------------------------
# EARLY "UNLOCK" CLICK  -> gentle popup
# ----------------------------------------------------------------------------
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
            f"({remaining} seconds remaining).",
            show_alert=True,
        )
    else:
        # Shouldn't normally happen (button swaps to 'confirm'), but be safe:
        await cb.answer("Playback complete — tap Confirm.", show_alert=True)


# ----------------------------------------------------------------------------
# CONFIRM -> silent wipe -> Phase 2
# ----------------------------------------------------------------------------
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
            f"({session['remaining']} seconds remaining).",
            show_alert=True,
        )
        return

    await cb.answer("Unlocking the Sanctuary…")

    # Stop the countdown task
    task = session.get("task")
    if task and not task.done():
        task.cancel()

    # --- SILENT BACKGROUND WIPE (bot's own messages for THIS user only) ---
    for mid in session.get("to_wipe", []):
        await safe_delete(user_id, mid)
        await asyncio.sleep(0.05)  # gentle pacing, avoids flood

    session["to_wipe"].clear()

    # --- Clean slate -> Phase 2 ---
    await bot.send_message(user_id, PHASE2_TEXT)

    # Reset the session, ready for a re-run
    USER_SESSIONS.pop(user_id, None)


# ----------------------------------------------------------------------------
# NOOP (the top, non-interactive button)
# ----------------------------------------------------------------------------
@dp.callback_query(F.data == "noop")
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer()


# ----------------------------------------------------------------------------
# HEALTH SERVER  (Render free tier needs an open port + external pinger)
# ----------------------------------------------------------------------------
async def health(_: web.Request) -> web.Response:
    return web.Response(text="Repellano bot is alive.")

async def start_web() -> None:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("Health server on :%s", port)


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
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
