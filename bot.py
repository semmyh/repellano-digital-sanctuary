import os
import logging
import time
import math
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("repellano")

# --- ENVIRONMENT CONFIGURATIONS ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@RDSTracks")

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
    "1️⃣ First, click the *Play button ▶️ above* to listen fully\.\n\n"
    "🔒 Then, return here and click *Unlock Sanctuary* below\."
)

USER_SESSIONS: dict[int, dict] = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

# --- HIGH-PRECISION SECURE TIMING LAYOUT ---
def secs_left(session: dict) -> int:
    end = session.get("end_time", 0.0)
    if not end:
        return 0
    # Uses a high-resolution monotonic interval calculation to fully close the cheat window
    return max(0, math.ceil(end - time.monotonic()))

# --- STEP 2 NAVIGATION KEYBOARDS ---
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version",  callback_data="lang:pidgin")],
    ])

def listening_keyboard(duration: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"▶️ Now Playing — {duration}s remaining", callback_data="noop")],
        [InlineKeyboardButton(text=f"🔒 Unlock Sanctuary ({duration}s)", callback_data="unlock")],
    ])

# --- STEP 1: /start COMMAND ---
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    name = message.from_user.first_name or "Leno"

    session = {"lang": None, "to_wipe": [], "end_time": 0}
    USER_SESSIONS[user_id] = session

    greeting = await message.answer(text=GREETING.format(name=name), reply_markup=lang_keyboard())
    session["to_wipe"].append(greeting.message_id)

# --- STEP 2: LOAD SONG & LYRICS ---
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
    
    # Store exact reference marker values securely into memory map
    session["end_time"] = time.monotonic() + cfg["duration"]

    # 1. Copy Audio Track Message from Channel
    try:
        audio_msg = await bot.copy_message(chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"])
        session["to_wipe"].append(audio_msg.message_id)
    except Exception as e:
        log.error("Audio copy failed: %s", e)
        await cb.message.answer("⚠️ Could not load track audio. Confirm bot channel permissions.")
        return

    # 2. Print Lyrics Card Node (Forced HTML Parsing Mode)
    lyrics_text = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    lyrics_msg = await bot.send_message(chat_id=user_id, text=lyrics_text, parse_mode=ParseMode.HTML)
    session["to_wipe"].append(lyrics_msg.message_id)

    # 3. Print Instructions Layout Block with Status Control Buttons
    instructions_msg = await bot.send_message(
        chat_id=user_id, 
        text=INSTRUCTIONS, 
        reply_markup=listening_keyboard(cfg["duration"])
    )
    session["to_wipe"].append(instructions_msg.message_id)

@dp.callback_query(F.data == "noop")
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer()

# --- STEP 3: ON-DEMAND ANTI-CHEAT GATEKEEPER ---
@dp.callback_query(F.data == "unlock")
async def on_unlock(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    session = USER_SESSIONS.get(user_id)

    if not session or session.get("lang") is None:
        await cb.answer("Session expired. Please execute /start to begin.", show_alert=True)
        return

    remaining = secs_left(session)

    if remaining > 0:
        # Secure shoulder-tap popup notification showing true single-digit remaining seconds instantly
        await cb.answer(
            f"🔒 Please listen fully to unlock the Sanctuary.\n"
            f"⏳ ({remaining} seconds remaining).", 
            show_alert=True
        )
    else:
        # Baseline validation path check passed successfully
        await cb.answer("✅ Playback time completed! Ready to move forward.", show_alert=True)

# --- WEB FRAMEWORK STATUS PORTS ---
async def health_handler(request):
    return web.Response(text="Server Online.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
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
    await asyncio.gather(
        start_web_server(),
        start_bot_polling()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
