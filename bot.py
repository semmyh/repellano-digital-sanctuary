import asyncio
import os
import time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, 
    CallbackQuery,
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAEe_3Hn-fQ-VHmcKMTdfXBIiC43b-lBGc0")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CHANNEL_ID = "@RDSTracks"

# Exact time locks and message IDs mapped out for synchronization
CONFIGS = {
    "en": {"msg_id": 6, "duration": 240, "title": "English"},
    "pidgin": {"msg_id": 15, "duration": 234, "title": "Pidgin"}
}

USER_SESSIONS = {}

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
    "<b>[Verse 1]</b>\nThe world market dey spin anyhow, e no dey stop\nForex trading sharp well-well, things just dey pop\nBut inside this Sanctuary, the vision clear pass glass\nWe dey commot the confusion, make the fear join pass\nWe dey change heavy lodu simple tool for everybody.\n\n"
    "<b>[Chorus]</b>\nE simple. E dey run on own. E dey for everyone.\nThirty-five FSSOs, the tech don change the run!\nPower dey for everybody, no matter where you start from\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\nEvery single heart\n\n"
    "<b>[Verse 2]</b>\nThe whole setup dey here to change how things suppose to be\nWhere math and market jam, things arrange properly\nThe system solid well-well, e smooth and e deep\nE dey work sharp-sharp inside silence when the world dey sleep.\n\n"
    "<b>[Verse 3]</b>\nThirty-five FSSOs stand gidigba, everything set well\nFinancial Support Service Offerings, na him we call FSSOs\nAutomated tools wey no dey tire or lose face\nTo support everybody wey dey struggle hard to find small money\n\n"
    "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nFinancial power for you, no matter where you start\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\n\n"
    "<b>[Outro]</b>\nThe Digital Sanctuary.\nWe don build, we don automate, we wan rise.\n[Fade Out][End]"
)

LYRICS_MAP = {"en": EN_LYRICS, "pidgin": PIDGIN_LYRICS}

def get_language_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_data="run_en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version", callback_data="run_pidgin")]
    ])

def get_verify_kb(lang: str, start_time: float, duration: int) -> InlineKeyboardMarkup:
    elapsed = time.time() - start_time
    if elapsed >= duration:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎧 Track Playback Complete", callback_data="instruction_only")],
            [InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_data="check_loop")]
        ])
    rem = int(duration - elapsed)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"First, Click Play Button ▶️ Above to Listen Fully [{rem}s]", 
            callback_data="timer_lock"
        )],
        [InlineKeyboardButton(
            text="🔒 Then, Return to Click Here and Unlock Sanctuary", 
            callback_data="timer_lock"
        )]
    ])

def get_listen_again_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yes, Listen Again", callback_data="choice_yes")],
        [InlineKeyboardButton(text="➡️ No, Proceed Forward", callback_data="choice_no")]
    ])

def get_replay_lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Replay English Version", callback_data="replay_en")],
        [InlineKeyboardButton(text="🎧 Replay Pidgin Version", callback_data="replay_pidgin")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_name = message.from_user.first_name
    await bot.set_chat_menu_button(chat_id=message.chat.id)
    await message.answer(
        f"Welcome, Dear {user_name}! To begin, take the first step. Choose your language version below to enjoy the Sanctuary's Anthem",
        reply_markup=get_language_menu(),
        parse_mode="HTML"
    )

async def deploy_anthem_assets(call: CallbackQuery, lang: str) -> None:
    cfg = CONFIGS.get(lang)
    user_id = call.from_user.id
    
    old_session = USER_SESSIONS.get(user_id)
    if old_session:
        try:
            await bot.delete_message(chat_id=user_id, message_id=old_session["audio_id"])
            await bot.delete_message(chat_id=user_id, message_id=old_session["lyrics_id"])
        except Exception:
            pass
            
    audio_msg = await bot.copy_message(chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"])
    start_timestamp = time.time()
    
    USER_SESSIONS[user_id] = {
        "lang": lang,
        "start": start_timestamp,
        "audio_id": audio_msg.message_id,
        "lyrics_id": None
    }
    
    txt = LYRICS_MAP.get(lang, EN_LYRICS)
    l_msg = await call.message.answer(txt, reply_markup=get_verify_kb(lang, start_timestamp, cfg["duration"]), parse_mode="HTML")
    USER_SESSIONS[user_id]["lyrics_id"] = l_msg.message_id

@dp.callback_query(F.data.startswith("run_"))
async def run_handler(call: CallbackQuery) -> None:
    lang = call.data.replace("run_", "")
    await call.answer("Accessing Sanctuary Anthem Assets...")
    await deploy_anthem_assets(call, lang)

@dp.callback_query(F.data == "instruction_only")
async def instruction_handler(call: CallbackQuery) -> None:
    await call.answer("Track validation confirmed. Click the green button below to check your progress status.", show_alert=True)

@dp.callback_query(F.data == "timer_lock")
async def timer_lock_handler(call: CallbackQuery) -> None:
    session = USER_SESSIONS.get(call.from_user.id)
    if not session:
        await call.answer("Session expired. Type /start to refresh.", show_alert=True)
        return
    cfg = CONFIGS.get(session["lang"])
    elapsed = time.time() - session["start"]
    
    try:
        await call.message.edit_reply_markup(reply_markup=get_verify_kb(session["lang"], session["start"], cfg["duration"]))
    except Exception:
        pass
    
    if elapsed >= cfg["duration"]:
        await call.answer("✨ Playback Complete! Tap the green button to check progress status.", show_alert=True)
    else:
        rem = int(cfg["duration"] - elapsed)
        await call.answer(f"🔒 Playback processing. Please listen fully. ({rem}s remaining)", show_alert=True)

@dp.callback_query(F.data == "check_loop")
async def check_loop_handler(call: CallbackQuery) -> None:
    session = USER_SESSIONS.get(call.from_user.id)
    if not session:
        return
        
    cfg = CONFIGS.get(session["lang"])
    elapsed = time.time() - session["start"]
    
    if elapsed < cfg["duration"]:
        await call.answer("🔒 Please listen fully before confirming.", show_alert=True)
        return
        
    await call.answer()
    await call.message.answer(
        "<b>🎵 Playback Verified Natively</b>\n\nWould you like to listen to the Sanctuary Anthem again before we proceed forward?",
        reply_markup=get_listen_again_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "choice_yes")
async def choice_yes_handler(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text(
        "<b>Select which version of the Sanctuary Anthem you would like to experience again:</b>",
        reply_markup=get_replay_lang_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("replay_"))
async def replay_handler(call: CallbackQuery) -> None:
    lang = call.data.replace("replay_", "")
    user_id = call.from_user.id
    session = USER_SESSIONS.get(user_id)
    await call.answer("Reloading Anthem Core...")
    
    if session and session["lang"] == str(lang):
        try:
            await call.message.delete()
        except Exception:
            pass
        cfg = CONFIGS.get(lang)
        session["start"] = time.time()
        try:
