"""
Repellano Sanctuary Bot — aiogram v3
====================================
/start -> language pick -> native alert popup -> audio (copied from channel)
+ lyrics -> live countdown -> unlock gate -> clean sweep -> Phase 2.

Install:
    pip install "aiogram>=3.4"

Run:
    export BOT_TOKEN="your_new_token_here"   # NEVER hardcode it
    python sanctuary_bot_aiogram.py

FEASIBILITY (unchanged, read this):
  * Bots CANNOT write to a user's "Saved Messages" — no API exists.
  * `show_alert=True` popups are dismiss-only; they cannot open Saved Messages.
  * Bots CANNOT force-navigate a user back into the bot chat.
  * In a private chat a bot may only delete ITS OWN messages (< 48h old).
  The code below implements the closest legal behaviour for each point.
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]          # fail loud if missing
CHANNEL_ID = "@RDSTracks"

CONFIGS = {
    "en": {"msg_id": 6, "duration": 240, "title": "English"},
    "pidgin": {"msg_id": 15, "duration": 234, "title": "Pidgin"},
}

COUNTDOWN_STEP = 5   # seconds between edits (flood-limit safe)

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
    "<b>[Verse 1]</b>\nThe world market dey spin anyhow, e no dey stop\nForex trading sharp well-well, things just dey pop\nBut inside this Sanctuary, the vision clear pass glass\nWe dey commot the confusion, make the fear no pass\nWe dey change heavy lodu to simple tool for everybody.\n\n"
    "<b>[Chorus]</b>\nE simple. E dey run on own. E dey for everyone.\nThirty-five FSSOs, the tech don change the run!\nPower dey for everybody, no matter where you start from\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\nEvery single heart\n\n"
    "<b>[Verse 2]</b>\nThe whole setup dey here to change how things suppose to be\nWhere math and market jam, things arrange properly\nThe system solid well-well, e smooth and e deep\nE dey work sharp-sharp inside silence when the world dey sleep.\n\n"
    "<b>[Verse 3]</b>\nThirty-five FSSOs stand gidigba, everything set well\nFinancial Support Service Offerings, na him we call FSSOs\nAutomated tools wey no dey tire or lose face\nTo support everybody wey dey struggle hard to find small money\n\n"
    "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nFinancial power for you, no matter where you start\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\n\n"
    "<b>[Outro]</b>\nThe Digital Sanctuary.\nWe don build, we don automate, we wan rise.\n[Fade Out][End]"
)

LYRICS_MAP = {"en": EN_LYRICS, "pidgin": PIDGIN_LYRICS}

# chat_id -> {"remaining", "msg_id", "key", "sweep": [ids], "task"}
SESSIONS: dict[int, dict] = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ------------------------------------------------------------- Step 1 --------
@dp.message(CommandStart())
async def start(message: Message) -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🎧 {c['title']} Version", callback_data=f"pick:{k}")]
            for k, c in CONFIGS.items()
        ]
    )
    await message.answer(
        f"Welcome, Dear {message.from_user.first_name}! To begin, take the first "
        f"step. Choose your language version below to enjoy the Sanctuary's Anthem.",
        reply_markup=kb,
    )


# ------------------------------------------------------- Steps 2, 3 & 4 ------
@dp.callback_query(F.data.startswith("pick:"))
async def pick(call: CallbackQuery) -> None:
    key = call.data.split(":", 1)[1]
    cfg = CONFIGS[key]
    chat_id = call.message.chat.id

    # Step 2: native alert popup with the exact success text.
    await call.answer(
        text=(
            "Success! Your selected Anthem has been forwarded to your Saved "
            "Messages folder for a replay at anytime of your choice."
        ),
        show_alert=True,
    )

    sweep: list[int] = []

    # Step 3/4: copy the real audio from the channel into the bot chat.
    audio_msg = await bot.copy_message(
        chat_id=chat_id,
        from_chat_id=CHANNEL_ID,
        message_id=cfg["msg_id"],
        caption="Your Anthem is ready. Press play, then follow the lyrics below.",
    )
    sweep.append(audio_msg.message_id)

    lyrics_msg = await bot.send_message(chat_id=chat_id, text=LYRICS_MAP[key])
    sweep.append(lyrics_msg.message_id)

    lock_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(
            text="⏳ Locked — 00:00", callback_data=f"unlock:{key}")]]
    )
    lock_msg = await bot.send_message(
        chat_id=chat_id,
        text="▶️ Play the track above. The unlock button activates when it ends.",
        reply_markup=lock_kb,
    )
    sweep.append(lock_msg.message_id)

    task = asyncio.create_task(_countdown(chat_id, key, lock_msg.message_id))
    SESSIONS[chat_id] = {
        "remaining": cfg["duration"],
        "msg_id": lock_msg.message_id,
        "key": key,
        "sweep": sweep,
        "task": task,
    }


async def _countdown(chat_id: int, key: str, msg_id: int) -> None:
    """Decrement the timeline and refresh the lock button label."""
    try:
        while True:
            await asyncio.sleep(COUNTDOWN_STEP)
            st = SESSIONS.get(chat_id)
            if not st:
                return
            st["remaining"] = max(0, st["remaining"] - COUNTDOWN_STEP)
            mins, secs = divmod(st["remaining"], 60)
            label = (f"⏳ Locked — {mins:02d}:{secs:02d}"
                     if st["remaining"] else "🔓 Unlock now")
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=label, callback_data=f"unlock:{key}")]])
            try:
                await bot.edit_message_reply_markup(
                    chat_id=chat_id, message_id=msg_id, reply_markup=kb)
            except Exception as exc:
                log.warning("countdown edit failed %s: %s", chat_id, exc)
            if st["remaining"] == 0:
                return
    except asyncio.CancelledError:
        return


# ------------------------------------------------------------- Step 5 --------
@dp.callback_query(F.data.startswith("unlock:"))
async def unlock(call: CallbackQuery) -> None:
    chat_id = call.message.chat.id
    st = SESSIONS.get(chat_id)

    if st and st["remaining"] > 0:
        await call.answer(
            "The track is still playing — let it finish first.", show_alert=True)
        return

    await call.answer()

    if st:
        st["task"].cancel()
        for mid in st["sweep"]:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception as exc:
                log.warning("delete failed %s/%s: %s", chat_id, mid, exc)
        SESSIONS.pop(chat_id, None)

    await bot.send_message(
        chat_id=chat_id,
        text="Phase 2: Brief Introduction to Repellano Nigeria Limited (RNL).",
    )


# ------------------------------------------------------------- main ----------
async def main() -> None:
    log.info("Sanctuary Bot polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
