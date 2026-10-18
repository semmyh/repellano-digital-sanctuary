import os
import logging
import time
import math
import asyncio
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("repellano")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAHO71GubQl4kvAIeT1dpI_NA2gsqKGS8eI").strip()
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

COMPLETE_TEXT = (
    "🎉 *Playback Complete\!\n\n"
    "Please tap below to finalize your validation check and unlock the next phase\."
)

PHASE2_TEXT = (
    "✅ *Welcome to the Sanctuary\.*\n\n"
    "📖 *Phase 2: Brief Introduction to Repellano Nigeria Limited \(RNL\)*\n\n"
    "Repellano Nigeria Limited \(RNL\) is established to drive innovations, "
    "secure local development opportunities, and provide structural excellence "
    "across all related domains\. Welcome aboard your onboarding journey\!"
)

USER_SESSIONS: dict[int, dict] = {}

bot = AsyncTeleBot(BOT_TOKEN)

# --- TIME ENGINE ---
def secs_left(session: dict) -> int:
    end = session.get("end_time", 0.0)
    if not end:
        return 0
    return max(0, math.ceil(end - time.monotonic()))

# --- KEYBOARDS ---
def lang_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en"),
        InlineKeyboardButton(text="🎧 Pidgin Version",  callback_data="lang:pidgin")
    )
    return markup

def listening_keyboard(duration: int) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text=f"🔒 Unlock Sanctuary ({duration}s)", callback_data="unlock"))
    return markup

def done_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(text="🎧 Track Playback Complete", callback_data="noop"),
        InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_data="confirm")
    )
    return markup

# --- TELEGRAM ROUTES ---
@bot.message_handler(commands=['start'])
async def cmd_start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name or "Leno"
    session = {"lang": None, "to_wipe": [], "remaining": 0, "end_time": 0}
    USER_SESSIONS[user_id] = session
    greeting = await bot.send_message(chat_id=user_id, text=GREETING.format(name=name), reply_markup=lang_keyboard(), parse_mode="MarkdownV2")
    session["to_wipe"].append(greeting.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang:"))
async def on_lang(call):
    lang = call.data.split(":", 1)[1]
    user_id = call.from_user.id
    session = USER_SESSIONS.get(user_id)
    if session is None:
        await bot.answer_callback_query(call.id, text="Please type /start to reset your session.", show_alert=True)
        return
    await bot.answer_callback_query(call.id)
    cfg = CONFIGS[lang]
    session["lang"] = lang
    session["end_time"] = time.monotonic() + cfg["duration"]

    try:
        audio_msg = await bot.copy_message(chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"])
        session["to_wipe"].append(audio_msg.message_id)
    except Exception as e:
        log.error("Audio copy failed: %s", e)
        await bot.send_message(chat_id=user_id, text="⚠️ Could not load track audio.")
        return

    lyrics_text = EN_LYRICS if lang == "en" else PIDGIN_LYRICS
    lyrics_msg = await bot.send_message(chat_id=user_id, text=lyrics_text, parse_mode="HTML")
    session["to_wipe"].append(lyrics_msg.message_id)

    instructions_msg = await bot.send_message(chat_id=user_id, text=INSTRUCTIONS, reply_markup=listening_keyboard(cfg["duration"]), parse_mode="MarkdownV2")
    session["to_wipe"].append(instructions_msg.message_id)
    session["control_msg_id"] = instructions_msg.message_id

@bot.callback_query_handler(func=lambda call: call.data == "unlock")
async def on_unlock(call):
    user_id = call.from_user.id
    session = USER_SESSIONS.get(user_id)
    if not session or session.get("lang") is None:
        await bot.answer_callback_query(call.id, text="Session expired. Please /start again.", show_alert=True)
        return
    remaining = secs_left(session)
    if remaining > 0:
        await bot.answer_callback_query(call.id, text=f"🔒 Please listen fully to unlock the Sanctuary.\n⏳ ({remaining} seconds remaining).", show_alert=True)
        return
    await bot.answer_callback_query(call.id, text="✅ Playback verified!", show_alert=True)
    try:
        await bot.edit_message_text(chat_id=user_id, message_id=session["control_msg_id"], text=COMPLETE_TEXT, reply_markup=done_keyboard(), parse_mode="MarkdownV2")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "confirm")
async def on_confirm(call):
    user_id = call.from_user.id
    session = USER_SESSIONS.get(user_id)
    if not session or session.get("lang") is None:
        await bot.answer_callback_query(call.id, text="Session expired. Please /start again.", show_alert=True)
        return
    if secs_left(session) > 0:
        await bot.answer_callback_query(call.id, text="🔒 Security error. Tracking time metrics incomplete.", show_alert=True)
        return
    await bot.answer_callback_query(call.id, text="Processing absolute clean sweep wipe...")
    for msg_id in session.get("to_wipe", []):
        try:
            await bot.delete_message(chat_id=user_id, message_id=msg_id)
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await bot.send_message(chat_id=user_id, text=PHASE2_TEXT, parse_mode="MarkdownV2")
    USER_SESSIONS.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data == "noop")
async def on_noop(call):
    await bot.answer_callback_query(call.id)

# --- WEB HEALTH SERVER ---
async def health_handler(request):
    return web.Response(text="Server Online.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
