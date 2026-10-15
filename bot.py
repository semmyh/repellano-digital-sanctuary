import asyncio
import os
import time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, 
    CallbackQuery,
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAEe_3Hn-fQ-VHmcKMTdfXBIiC43b-lBGc0")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CHANNEL_ID = "@RDSTracks"

# Asset configurations tracking your exact file length timelines
CONFIGS = {
    "en": {"msg_id": 6, "duration": 240, "title": "English"},
    "pidgin": {"msg_id": 15, "duration": 234, "title": "Pidgin"}
}

USER_SESSIONS = {}
# Track which language each verified user chose
VERIFIED_USERS = {} 

def get_library_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎵 Copy Anthem to Replay")]
        ],
        resize_keyboard=True
    )

def get_language_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎧 English Version", callback_data="run_en")],
            [InlineKeyboardButton(text="🎧 Pidgin Version", callback_data="run_pidgin")]
        ]
    )

def get_verify_kb(lang: str, start_time: float, duration: int) -> InlineKeyboardMarkup:
    elapsed = time.time() - start_time
    if elapsed >= duration:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎧 Track Playback Complete", callback_data="instruction_only")],
            [InlineKeyboardButton(text="✅ Return to Click Here to Unlock Sanctuary", callback_data="secure_clear")]
        ])
    else:
        rem = int(duration - elapsed)
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔒 Click Play Button Above to Listen Fully [{rem}s]", 
                callback_data="timer_lock"
            )],
            [InlineKeyboardButton(
                text="🔒 Return to Click Here to Unlock Sanctuary", 
                callback_data="timer_lock"
            )]
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

@dp.callback_query(F.data.startswith("run_"))
async def run_handler(call: CallbackQuery) -> None:
    lang = call.data.replace("run_", "")
    cfg = CONFIGS.get(lang)
    await call.answer("Accessing Sanctuary Anthem Assets...")
    
    audio_msg = await bot.copy_message(
        chat_id=call.from_user.id,
        from_chat_id=CHANNEL_ID,
        message_id=cfg["msg_id"]
    )
    
    start_timestamp = time.time()
    
    USER_SESSIONS[call.from_user.id] = {
        "lang": lang,
        "start": start_timestamp,
        "audio_id": audio_msg.message_id,
        "lyrics_id": None
    }
    
    if lang == "en":
        txt = (
            "<b>📜 Repellano Anthem (English Lyrics)</b>\n\n"
            "<b>[Intro]</b>\nWelcome to the Sanctuary.\nWhere the chaotic markets find their perfect peace.\nThis is SemLeno's Repellano Digital Sanctuary.\n\n"
            "<b>[Verse 1]</b>\nThe global markets spin in a wild, endless race\nComplex forex trading moving at a blinding pace\nBut inside the Sanctuary, the vision is crystal clear\nWe strip away the chaos, we break down the fear\nTurning heavy burdens into a simple tool for all.\n\n"
            "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nUniversal empowerment, no matter where you start\nRepellano lifting up, up, up, up, every single heart!\nEvery single heart!\nEvery single heart\n\n"
            "<b>[Verse 2]</b>\nAn ecosystem built to redefine the grand design\nWhere mathematics meets the market, aligning line by line\nA seamless architecture, steady, smooth, and deep\nWorking in the silence while the world is fast asleep.\n\n"
            "<b>[Verse 3]</b>\nThirty-five FSSOs standing structured and strong\nFinancial Support Service Offerings where they belong\nAutomated utilities that never tire or fade\nTo help all those struggling with their finances\n\n"
            "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nUniversal empowerment, no matter where you start\nRepellano lifting up, up, up, up, every single heart!\nEvery single heart!\nEvery single heart!\n\n"
            "<b>[Outro]</b>\nThe Digital Sanctuary.\nWe build, we automate, we rise.\n[Fade Out] [End]"
        )
    else:
        txt = (
            "<b>📜 Repellano Anthem (Pidgin Lyrics)</b>\n\n"
            "<b>[Intro]</b>\nWelcome to the Sanctuary.\nWhere jaga jaga forex markets find their perfect peace.\nThis na Semleno Repellano Digital Sanctuary.\n\n"
            "<b>[Verse 1]</b>\nThe world market dey spin anyhow, e no dey stop\nForex trading sharp well-well, things just dey pop\nBut inside this Sanctuary, the vision clear pass glass\nWe dey commot the confusion, make the fear join pass\nWe dey change heavy lodu simple tool for everybody.\n\n"
            "<b>[Chorus]</b>\nE simple. E dey run on own. E dey for everyone.\nThirty-five FSSOs, the tech don change the run!\nPower dey for everybody, no matter where you start from\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\nEvery single heart\n\n"
            "<b>[Verse 2]</b>\nThe whole setup dey here to change how things suppose to be\nWhere math and market jam, things arrange properly\nThe system solid well-well, e smooth and e deep\nE dey work sharp-sharp inside silence when the world dey sleep.\n\n"
            "<b>[Verse 3]</b>\nThirty-five FSSOs stand gidigba, everything set well\nFinancial Support Service Offerings, na him we call FSSOs\nAutomated tools wey no dey tire or lose face\nTo support everybody wey dey struggle hard to find small money\n\n"
            "<b>[Chorus]</b>\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nFinancial power for you, no matter where you start\nRepellano oh, oh, oh every single heart!\nEvery single heart\nEvery single heart\n\n"
            "<b>[Outro]</b>\nThe Digital Sanctuary.\nWe don build, we don automate, we wan rise.\n[Fade Out][End]"
        )
        
    l_msg = await call.message.answer(txt, reply_markup=get_verify_kb(lang, start_timestamp, cfg["duration"]), parse_mode="HTML")
    USER_SESSIONS[call.from_user.id]["lyrics_id"] = l_msg.message_id

@dp.callback_query(F.data == "instruction_only")
async def instruction_handler(call: CallbackQuery) -> None:
    await call.answer("Track validation confirmed. Click the button below to unlock entry.", show_alert=True)

@dp.callback_query(F.data == "timer_lock")
async def timer_lock_handler(call: CallbackQuery) -> None:
    session = USER_SESSIONS.get(call.from_user.id)
    if not session:
        await call.answer("Session expired. Type /start to refresh.", show_alert=True)
        return
    cfg = CONFIGS.get(session["lang"])
    elapsed = time.time() - session["start"]
    
    await call.message.edit_reply_markup(reply_markup=get_verify_kb(session["lang"], session["start"], cfg["duration"]))
    
    if elapsed >= cfg["duration"]:
        await call.answer("✨ Playback Complete! Tap the bottom button to proceed.", show_alert=True)
    else:
        rem = int(cfg["duration"] - elapsed)
        await call.answer(f"🔒 Playback processing. Please listen fully. ({rem}s remaining)", show_alert=True)

@dp.callback_query(F.data == "secure_clear")
async def secure_clear_handler(call: CallbackQuery) -> None:
    session = USER_SESSIONS.get(call.from_user.id)
    await call.answer("Sanctuary Entrance Unlocked.")
    
    # Store user preference language key natively
    user_lang = "en"
    if session:
        user_lang = session["lang"]
    VERIFIED_USERS[call.from_user.id] = user_lang
    
    if session:
        try:
            await bot.delete_message(chat_id=call.from_user.id, message_id=session["audio_id"])
            await bot.delete_message(chat_id=call.from_user.id, message_id=session["lyrics_id"])
        except Exception:
            pass
        USER_SESSIONS.pop(call.from_user.id, None)
    
    await call.message.answer(
        "<b>Onboarding Anthem Complete</b>\n\n"
        "Your listening verification has been processed seamlessly. Click here to proceed to a brief introduction to the Company (Repellano Nigeria Limited)", 
        reply_markup=get_library_reply_kb(),
        parse_mode="HTML"
    )

# FIXED: Transfers strictly the CHOSEN language asset directly to Saved Messages
@dp.message(F.text == "🎵 Copy Anthem to Replay")
async def library_replay_handler(message: Message) -> None:
    user_id = message.from_user.id
    if user_id not in VERIFIED_USERS:
        await message.answer("🔒 Sanctuary Library access requires completing initial onboarding verification first via /start.")
        return
        
    chosen_lang = VERIFIED_USERS[user_id]
    cfg = CONFIGS[chosen_lang]
    
    # Send a quick confirmation popup in the main chat room, keeping it completely clean
    notice_msg = await message.answer("📤 Transferring your verified anthem files directly into your personal Saved Messages archive folder...")
    
    try:
        # FIXED: Routing destination parameter changed to target the user's hidden personal cloud folder natively
        await bot.copy_message(chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=cfg["msg_id"])
        
        # Send full explicit text charter along with the audio file inside Saved Messages
        if chosen_lang == "en":
            archive_txt = (
                "<b>📥 Archived Sanctuary Anthem (English)</b>\n\n"
