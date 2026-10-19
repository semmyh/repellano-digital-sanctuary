"""
STEP 3 — CORRECTED: Active Timer + Anti-Cheat Gatekeeper
Drop-in replacements for the relevant parts of your Repellano bot.

Fixes:
  1. time.time()  -> time.monotonic()   (immune to wall-clock jumps)
  2. int()        -> math.ceil()        (closes the ~1s cheat window)
  3. on_lang now cancels the previous task (no orphan timers)
  4. single source of truth for end_time + a `completed` flag
  5. safe_edit reports "message gone" so the loop can stop after a wipe
"""

import math
import time
import asyncio

from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest


# ---------------------------------------------------------------------------
# SINGLE SOURCE OF TRUTH FOR THE COUNTDOWN
# ---------------------------------------------------------------------------
def secs_left(session: dict) -> int:
    """
    Strict remaining seconds.
    ceil() means ANY fraction > 0 still blocks -> no sub-second cheat window.
    """
    end = session.get("end_time", 0.0)
    if not end:
        return 0
    return max(0, math.ceil(end - time.monotonic()))


# ---------------------------------------------------------------------------
# SAFE EDIT — now tells the caller when the message no longer exists
# ---------------------------------------------------------------------------
async def safe_edit(chat_id: int, message_id: int, text: str, markup) -> bool:
    """Returns True if the edit landed (or was a harmless no-op).
       Returns False if the message is gone -> countdown should stop."""
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=text, reply_markup=markup,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return True
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=text, reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return True
        except Exception:
            return False
    except TelegramBadRequest as e:
        # "message is not modified" is normal when the text is identical
        if "message is not modified" in str(e):
            return True
        return False  # deleted / not found -> stop the loop
    except Exception:
        return False


# ---------------------------------------------------------------------------
# THE BACKGROUND COUNTDOWN ENGINE
# ---------------------------------------------------------------------------
async def run_countdown(user_id: int, message_id: int, session: dict) -> None:
    me = asyncio.current_task()

    while True:
        await asyncio.sleep(TICK)  # non-blocking; never time.sleep()

        # Session was replaced (/start) or task was cancelled -> die quietly
        if USER_SESSIONS.get(user_id) is not session or session.get("task") is not me:
            return

        remaining = secs_left(session)
        session["remaining"] = remaining

        if remaining <= 0:
            session["completed"] = True
            # STEP 4 hook: morph the buttons the instant playback ends
            await safe_edit(user_id, message_id, COMPLETE_TEXT, complete_keyboard())
            return

        ok = await safe_edit(user_id, message_id, INSTRUCTIONS,
                             listening_keyboard(remaining))
        if not ok:      # message wiped / deleted -> stop cleanly
            return


# ---------------------------------------------------------------------------
# STEP 2 HANDLER — cancel any previous timer before starting a new one
# ---------------------------------------------------------------------------
@dp.callback_query(F.data.startswith("lang:"))
async def on_lang(cb: CallbackQuery) -> None:
    lang = cb.data.split(":", 1)[1]
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)

    if session is None:
        await cb.answer("Please type /start to reset your session.", show_alert=True)
        return

    await cb.answer()
    cfg = CONFIGS[lang]

    # FIX: kill the old timer instead of silently overwriting the reference
    old = session.get("task")
    if old and not old.done():
        old.cancel()

    session["lang"] = lang
    session["completed"] = False
    session["end_time"] = time.monotonic() + cfg["duration"]   # monotonic!
    session["remaining"] = cfg["duration"]

    try:
        audio_msg = await bot.copy_message(
            chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"])
        session["to_wipe"].append(audio_msg.message_id)
    except Exception as e:
        log.error("Audio execution failed: %s", e)
        await cb.message.answer("⚠️ Could not load track audio.")
        return

    lyrics_text = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    lyrics_msg = await cb.message.answer(text=lyrics_text)
    session["to_wipe"].append(lyrics_msg.message_id)

    instructions_msg = await cb.message.answer(
        text=INSTRUCTIONS, reply_markup=listening_keyboard(cfg["duration"]))
    session["to_wipe"].append(instructions_msg.message_id)

    session["task"] = asyncio.create_task(
        run_countdown(user_id, instructions_msg.message_id, session))


# ---------------------------------------------------------------------------
# STEP 3 — ANTI-CHEAT GATEKEEPER
# ---------------------------------------------------------------------------
@dp.callback_query(F.data == "unlock")
async def on_unlock(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)

    if not session or session.get("lang") is None:
        await cb.answer("Session expired. Please /start again.", show_alert=True)
        return

    remaining = secs_left(session)

    if remaining > 0:
        # real-time shoulder tap, down to the single digit
        await cb.answer(
            f"🔒 Please listen fully to unlock the Sanctuary.\n"
            f"⏳ {remaining} second(s) remaining.",
            show_alert=True,
        )
        return

    session["completed"] = True
    await cb.answer("✅ Playback verified!", show_alert=True)
    # >>> STEP 4 WIPE + "Phase 2" message goes here <<<
