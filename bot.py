import os
import logging
import asyncio
import time
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramRetryAfter
from aiohttp import web

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("repellano")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAHO71GubQl4kvAIeT1dpI_NA2gsqKGS8eI").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@RDSTracks")

# UI refresh rhythm to bypass Telegram Flood limits on a free tier instance.
TICK = 5 

CONFIGS = {
    "en":     {"msg_id": 6,  "duration": 240, "title": "English"},
    "pidgin": {"msg_id": 15, "duration": 234, "title": "Pidgin"},
}

GREETING = (
    "Welcome, Dear *{name}*\!\n\n"
    "To begin, take the first step\. Choose your language version "
    "below to enjoy the Sanctuary's Anthem\."
)

EN_LYRICS = (
    "📜 *Repellano Anthem \(English Lyrics\)*\n\n"
    "*\[Intro\]*\nWelcome to the Sanctuary\.\nWhere the chaotic markets find their perfect peace\.\nThis is SemLeno's Repellano Digital Sanctuary\.\n\n"
    "*\[Verse 1\]*\nThe global markets spin in a wild, endless race\nComplex forex trading moving at a blinding pace\nBut inside the Sanctuary, the vision is crystal clear\nWe strip away the chaos, we break down the fear\nTurning heavy burdens into a simple tool for all\.\n\n"
    "*\[Chorus\]*\nSimple\. Automated\. Universal\.\nThirty\-five FSSOs, the tech reversal\!\nUniversal empowerment, no matter where you start\nRepellano lifting up, up, up, up, every single heart\!\nEvery single heart\!\nEvery single heart\n\n"
    "*\[Verse 2\]*\nAn ecosystem built to redefine the grand design\nWhere mathematics meets the market, aligning line by line\nA seamless architecture, steady, smooth, and deep\nWorking in the silence while the world is fast asleep\.\n\n"
    "*\[Verse 3\]*\nThirty\-five FSSOs standing structured and strong\nFinancial Support Service Offerings where they belong\nAutomated utilities that never tire or fade\nTo help all those struggling with their finances\n\n"
    "*\[Chorus\]*\nSimple\. Automated\. Universal\.\nThirty\-five FSSOs, the tech reversal\!\nUniversal empowerment, no matter where you start\nRepellano lifting up, up, up, up, every single heart\!\nEvery single heart\!\nEvery single heart\!\n\n"
    "*\[Outro\]*\nThe Digital Sanctuary\.\nWe build, we automate, we rise\.\n\[Fade Out\] \[End\]"
)

PIDGIN_LYRICS = (
    "📜 *Repellano Anthem \(Pidgin Lyrics\)*\n\n"
    "*\[Intro\]*\nWelcome to the Sanctuary\.\nWhere jaga jaga forex markets find their perfect peace\.\nThis na Semleno Repellano Digital Sanctuary\.\n\n"
    "*\[Verse 1\]*\nThe world market dey spin anyhow, e no dey stop\nForex trading sharp well\-well, things just dey pop\nBut inside this Sanctuary, the vision clear pass glass\nWe dey commot the confusion, make the fear join pass\nWe dey change heavy lodu simple tool for everybody\.\n\n"
    "*\[Chorus\]*\nE simple\. E dey run on own\. E dey for everyone\.\nThirty\-five FSSOs, the tech don change the run\!\nPower dey for everybody, no matter where you start from\nRepellano oh, oh, oh every single heart\!\nEvery single heart\nEvery single heart\nEvery single heart\n\n"
    "*\[Verse 2\]*\nThe whole setup dey here to change how things suppose to be\nWhere math and market jam, things arrange properly\nThe system solid well\-well, e smooth and e deep\nE dey work sharp\-sharp inside silence when the world dey sleep\.\n\n"
    "*\[Verse 3\]*\nThirty\-five FSSOs stand gidigba, everything set well\nFinancial Support Service Offerings, na him we call FSSOs\nAutomated tools wey no dey tire or lose face\nTo support everybody wey dey struggle hard to find small money\n\n"
    "*\[Chorus\]*\nSimple\. Automated\. Universal\.\nThirty\-five FSSOs, the tech reversal\!\nFinancial power for you, no matter where you start\nRepellano oh, oh, oh every single heart\!\nEvery single heart\nEvery single heart\n\n"
    "*\[Outro\]*\nThe Digital Sanctuary\.\nWe don build, we don automate, we wan rise\.\n\[Fade Out\]\[End\]"
)

INSTRUCTIONS = (
    "1️⃣ First, click the *Play button ▶️ above* to listen fully\.\n\n"
    "🔒 Then, return here and click *Unlock Sanctuary* below\."
)

USER_SESSIONS: dict[int, dict] = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

# --- SECURITY UTILITIES ---
async def safe_edit(chat_id: int, message_id: int, text: str, markup) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                                    text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN_V2)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, 
                                        text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception:
            pass
    except Exception:
        pass

# --- KEYBOARDS ---
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version",  callback_data="lang:pidgin")],
    ])

def listening_keyboard(remaining: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"▶️ Now Playing — {remaining}s remaining", callback_data="noop")],
        [InlineKeyboardButton(text=f"🔒 Unlock Sanctuary ({remaining}s)", callback_data="unlock")],
    ])

# --- BACKGROUND COUNTDOWN ENGINE ---
async def run_countdown(user_id: int, message_id: int, duration: int) -> None:
    start_time = time.time()
    end_time = start_time + duration

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
                text="🎵 *Sanctuary Anthem Playback Finished\!*\nPlease select unlock option below\.",
                markup=listening_keyboard(0)
            )
            break
        else:
            await safe_edit(
                chat_id=user_id,
                message_id=message_id,
                text=INSTRUCTIONS,
                markup=listening_keyboard(remaining)
            )

# --- COMMAND ROUTE ---
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    name = message.from_user.first_name or "Leno"

    old = USER_SESSIONS.pop(user_id, None)
    if old and old.get("task") and not old["task"].done():
        old["task"].cancel()

    session = {"lang": None, "to_wipe": [], "task": None, "remaining": 0, "end_time": 0}
    USER_SESSIONS[user_id] = session

    greeting = await message.answer(text=GREETING.format(name=name), reply_markup=lang_keyboard())
    session["to_wipe"].append(greeting.message_id)

# --- CUSTOM CALLBACK HANDLERS ---
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
    session["lang"] = lang
    session["remaining"] = cfg["duration"]
    session["end_time"] = time.time() + cfg["duration"]

    try:
        audio_msg = await bot.copy_message(chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"])
        session["to_wipe"].append(audio_msg.message_id)
    except Exception as e:
        log.error("Audio execution failed: %s", e)
        await cb.message.answer("⚠️ Could not load track audio. Confirm permissions configuration.")
        return

    lyrics_text = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    lyrics_msg = await cb.message.answer(text=lyrics_text)
    session["to_wipe"].append(lyrics_msg.message_id)

    instructions_msg = await cb.message.answer(text=INSTRUCTIONS, reply_markup=listening_keyboard(cfg["duration"]))
    session["to_wipe"].append(instructions_msg.message_id)

    session["task"] = asyncio.create_task(run_countdown(user_id, instructions_msg.message_id, cfg["duration"]))

@dp.callback_query(F.data == "unlock")
async def on_unlock(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)
    
    if not session:
        await cb.answer("Session expired. Please execute /start.", show_alert=True)
        return

    if session.get("end_time", 0) > 0:
        now = time.time()
        remaining = int(max(0, session["end_time"] - now))
        session["remaining"] = remaining
    else:
        remaining = session.get("remaining", 0)

    if remaining > 0:
        await cb.answer(
            f"🔒 Please listen fully to unlock the Sanctuary.\n({remaining} seconds remaining).", 
            show_alert=True
        )
    else:
        await cb.answer("Playback verification check complete!", show_alert=True)

@dp.callback_query(F.data == "noop")
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer()

# --- WEB WORKER ASYNC INTERFACE ROUTINES ---
async def health(_: web.Request) -> web.Response:
    return web.Response(text="Server Active.")

# --- INITIATION ROUTINE SYSTEM ---
async def main() -> None:
