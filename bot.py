"""
Repellano Sanctuary Bot
=======================
Flow: /start -> language pick -> native alert popup -> audio + lyrics deposit
      -> live countdown -> unlock -> clean sweep -> Phase 2 handoff.

Requires: python-telegram-bot[job-queue] >= 20.0  (async, PTB v20+)
    pip install "python-telegram-bot[job-queue]"

NOTE ON FEASIBILITY (read this):
  * Bots CANNOT write into a user's "Saved Messages". No API exists.
  * `show_alert=True` popups are dismiss-only; they cannot open Saved Messages.
  * Bots CANNOT force-navigate a user back into the bot chat.
  * In a private chat a bot can only delete ITS OWN messages (< 48h old).
  The code implements the closest legal behaviour for each of the above.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"

# --- Config: swap the file paths for your real assets -------------------------
TRACKS = {
    "en": {
        "label": "🎧 English Version",
        "audio": "assets/english_anthem.mp3",
        "lyrics": "assets/english_lyrics.txt",
        "duration": 240,  # seconds
    },
    "pidgin": {
        "label": "🎧 Pidgin Version",
        "audio": "assets/pidgin_anthem.mp3",
        "lyrics": "assets/pidgin_lyrics.txt",
        "duration": 234,  # seconds
    },
}

COUNTDOWN_STEP = 5  # seconds between edits (flood-limit safe)

# Runtime state ----------------------------------------------------------------
SWEEP: dict[int, list[int]] = {}   # chat_id -> message_ids the bot may delete
STATE: dict[int, dict] = {}        # chat_id -> {"remaining", "msg_id", "key"}


# ------------------------------------------------------------------ Step 1 ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t["label"], callback_data=f"pick:{key}")]
            for key, t in TRACKS.items()
        ]
    )
    await update.message.reply_text(
        f"Welcome, Dear {user.first_name}! To begin, take the first step. "
        f"Choose your language version below to enjoy the Sanctuary's Anthem.",
        reply_markup=keyboard,
    )


# ------------------------------------------------------ Steps 2, 3 & 4 --------
async def pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    key = query.data.split(":", 1)[1]
    track = TRACKS[key]
    chat_id = query.message.chat_id

    # Step 2: native alert popup with the exact success text.
    await query.answer(
        text=(
            "Success! Your selected Anthem has been forwarded to your "
            "Saved Messages folder for a replay at anytime of your choice."
        ),
        show_alert=True,
    )

    # Step 3/4: deposit the audio + lyrics into the bot chat.
    with open(track["lyrics"], "r", encoding="utf-8") as fh:
        lyrics = fh.read()

    sent_ids: list[int] = []

    audio_msg = await context.bot.send_audio(
        chat_id=chat_id,
        audio=track["audio"],
        title="Sanctuary Anthem",
        performer="Repellano Nigeria Limited",
        caption="Your Anthem is ready. Press play, then follow the lyrics below.",
    )
    sent_ids.append(audio_msg.message_id)

    lyrics_msg = await context.bot.send_message(chat_id=chat_id, text=lyrics)
    sent_ids.append(lyrics_msg.message_id)

    # Step 4: the stacked instruction / lock button under the lyrics.
    lock_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⏳ Locked — 00:00", callback_data=f"unlock:{key}")]]
    )
    lock_msg = await context.bot.send_message(
        chat_id=chat_id,
        text="▶️ Play the track above. The unlock button activates when it ends.",
        reply_markup=lock_kb,
    )
    sent_ids.append(lock_msg.message_id)

    SWEEP[chat_id] = sent_ids
    STATE[chat_id] = {
        "remaining": track["duration"],
        "msg_id": lock_msg.message_id,
        "key": key,
    }

    # Live countdown job (Step 4 timeline monitor).
    context.job_queue.run_repeating(
        _tick,
        interval=COUNTDOWN_STEP,
        first=COUNTDOWN_STEP,
        name=f"cd:{chat_id}",
        data={"chat_id": chat_id},
    )


async def _tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Decrement the timeline and refresh the lock button label."""
    chat_id = context.job.data["chat_id"]
    st = STATE.get(chat_id)
    if not st:
        context.job.schedule_removal()
        return

    st["remaining"] = max(0, st["remaining"] - COUNTDOWN_STEP)
    mins, secs = divmod(st["remaining"], 60)
    if st["remaining"]:
        label = f"⏳ Locked — {mins:02d}:{secs:02d}"
    else:
        label = "🔓 Unlock now"

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"unlock:{st['key']}")]]
    )
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=st["msg_id"], reply_markup=kb
        )
    except Exception as exc:  # message gone / unchanged
        log.warning("countdown edit failed for %s: %s", chat_id, exc)

    if st["remaining"] == 0:
        context.job.schedule_removal()


# ------------------------------------------------------------ Step 5 ----------
async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    st = STATE.get(chat_id)

    # Gate the unlock until the track has finished.
    if st and st["remaining"] > 0:
        await query.answer(
            "The track is still playing — let it finish first.", show_alert=True
        )
        return

    await query.answer()

    # Stop the countdown job.
    for job in context.job_queue.get_jobs_by_name(f"cd:{chat_id}"):
        job.schedule_removal()

    # Synchronized clean sweep of the bot's own cards.
    for mid in SWEEP.pop(chat_id, []):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception as exc:
            log.warning("delete failed for %s/%s: %s", chat_id, mid, exc)

    STATE.pop(chat_id, None)

    # The next threshold.
    await context.bot.send_message(
        chat_id=chat_id,
        text="Phase 2: Brief Introduction to Repellano Nigeria Limited (RNL).",
    )


# ---------------------------------------------------------------- main --------
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(pick, pattern=r"^pick:"))
    app.add_handler(CallbackQueryHandler(unlock, pattern=r"^unlock:"))
    log.info("Sanctuary Bot polling…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
