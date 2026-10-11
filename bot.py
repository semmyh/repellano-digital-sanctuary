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
    MenuButtonWebApp, 
    WebAppInfo
)
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAEe_3Hn-fQ-VHmcKMTdfXBIiC43b-lBGc0")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BASE_URL = "https://vercel.app"
CHANNEL_ID = "@RDSTracks"

# 1. Enforced Time Lock Settings (Calculated from your Track Lengths)
TRACK_CONFIGS = {
    "en": {"msg_id": 6, "duration": 240, "name": "English"},   # 03:60 -> 4 minutes flat
    "pidgin": {"msg_id": 7, "duration": 225, "name": "Pidgin"} # 03:45 -> 3 mins 45 secs
}

# 2. Complete 7-Block Lyrical Core Blueprint
ANTHEM_LYRICS = {
    "en": [
        "<b>[1/7] Intro</b>\n\n(Atmospheric tech synths open, steady afrobeat kicks in)\nWelcome to the Sanctuary.\nWhere the chaotic markets find their perfect peace.\nThis is SemLeno's Repellano Digital Sanctuary.",
        "<b>[2/7] Verse 1</b>\n\nThe global markets spin in a wild, endless race\nComplex forex trading moving at a blinding pace\nBut inside the Sanctuary, the vision is crystal clear\nWe strip away the chaos, we break down the fear\nTurning heavy burdens into a simple tool for all.",
        "<b>[3/7] Chorus</b>\n\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nUniversal empowerment, no matter where you start\nRepellano lifting up, up, up, up, every single heart!\nEvery single heart!\nEvery single heart",
        "<b>[4/7] Verse 2</b>\n\nAn ecosystem built to redefine the grand design\nWhere mathematics meets the market, aligning line by line\nA seamless architecture, steady, smooth, and deep\nWorking in the silence while the world is fast asleep.",
        "<b>[5/7] Verse 3</b>\n\nThirty-five FSSOs standing structured and strong\nFinancial Support Service Offerings where they belong\nAutomated utilities that never tire or fade\nTo help all those struggling with their finances",
        "<b>[6/7] Chorus</b>\n\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nUniversal empowerment, no matter where you start\nRepellano lifting up, up, up, up, every single heart!\nEvery single heart!\nEvery single heart!",
        "<b>[7/7] Outro</b>\n\nThe Digital Sanctuary.\nWe build, we automate, we rise.\n[Fade Out] [End]"
    ],
    "pidgin": [
        "<b>[1/7] Intro</b>\n\nWelcome to the Sanctuary.\nWhere jaga jaga forex markets find their perfect peace.\nThis na Semleno Repellano Digital Sanctuary.",
        "<b>[2/7] Verse 1</b>\n\nThe world market dey spin anyhow, e no dey stop\nForex trading sharp well-well, things just dey pop\nBut inside this Sanctuary, the vision clear pass glass\nWe dey commot the confusion, make the fear join pass\nWe dey change heavy loaduu, to simple tool for everybody.",
        "<b>[3/7] Chorus</b>\n\nE simple. E dey run on own. E dey for everyone.\nThirty-five FSSOs, the tech don change the run!\nPower dey for everybody, no matter where you start from\nRepellano oh, oh, oh, every single heart!\nEvery single heart!\nEvery single heart!\nEvery single heart!",
        "<b>[4/7] Verse 2</b>\n\nThe whole setup dey here to change how things suppose to be\nWhere math and market jam, things arrange properly\nThe system solid well-well, e smooth and e deep\nE dey work sharp-sharp inside silence when the world dey sleep.",
        "<b>[5/7] Verse 3</b>\n\nThirty-five FSSOs stand gidigba, everything set well\nFinancial Support Service Offerings, na him we call FSSOs\nAutomated tools wey no dey tire or lose face\nTo support everybody wey dey struggle hard to find small money",
        "<b>[6/7] Chorus</b>\n\nSimple. Automated. Universal.\nThirty-five FSSOs, the tech reversal!\nUniversal empowerment, no matter where you start\nRepellano lifting all, all, all, all, every single heart!\nEvery single heart!\nEvery single heart!",
        "<b>[7/7] Outro</b>\n\nThe Digital Sanctuary.\nWe build, we automate, we rise.\n[Fade Out] [End]"
    ]
}

# Tracking dictionary to securely check timelines and active interface states
USER_SESSIONS = {}

def get_language_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎧 English Version", callback_data="start_aof:en")],
            [InlineKeyboardButton(text="🎧 Pidgin Version", callback_data="start_aof:pidgin")]
        ]
    )

def get_pagination_kb(lang: str, current_idx: int, start_time: float, target_duration: int) -> InlineKeyboardMarkup:
    buttons = []
    
    # Navigation arrows row layout
    nav_row = []
    if current_idx > 0:
        nav_row.append(InlineKeyboardButton(text="← Back", callback_data=f"page:{lang}:{current_idx-1}"))
    if current_idx < 6:
        nav_row.append(InlineKeyboardButton(text="Next Section ➔", callback_data=f"page:{lang}:{current_idx+1}"))
    if nav_row:
        buttons.append(nav_row)
        
    # Enforced Gatekeeper Lock check evaluation loop
    if current_idx == 6:
        elapsed = time.time() - start_time
        if elapsed >= target_duration:
            buttons.append([InlineKeyboardButton(text="✅ Confirm Listening Fully", callback_data="confirm_completion")])
        else:
            remaining = int(target_duration - elapsed)
            buttons.append([InlineKeyboardButton(text=f"🔒 Listen Fully to Unlock ({remaining}s)", callback_data="check_timer")])
            
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_name = message.from_user.first_name
    
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(text="🛡️ Sanctuary Gate", web_app=WebAppInfo(url=BASE_URL))
    )
    
    # REQUIREMENT 1 COPY SPECIFICATIONS
    await message.answer(
        f"Welcome, Dear {user_name}! To begin, take the first step. Choose your language version below to enjoy the Sanctuary's Anthem",
        reply_markup=get_language_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("start_aof:"))
async def start_aof_handler(call: CallbackQuery) -> None:
    lang = call.data.split(":")[1]
    config = TRACKS_CONFIGS[lang]
    
    await call.answer("Deploying Anthem Core...")
    
    # Deliver the cloud audio post file natively into chat log views
    audio_msg = await bot.copy_message(
        chat_id=call.from_user.id,
        from_chat_id=CHANNEL_ID,
        message_id=config["msg_id"]
    )
    
    # Launch tracking blueprint parameter vectors
    USER_SESSIONS[call.from_user.id] = {
        "lang": lang,
        "start_time": time.time(),
        "audio_msg_id": audio_msg.message_id,
        "lyrics_msg_id": None
    }
    
    # Deliver first lyrical slide box frame
    lyrics_msg = await call.message.answer(
        ANTHEM_LYRICS[lang][0],
        reply_markup=get_pagination_kb(lang, 0, time.time(), config["duration"]),
        parse_mode="HTML"
    )
    
    USER_SESSIONS[call.from_user.id]["lyrics_msg_id"] = lyrics_msg.message_id

@dp.callback_query(F.data.startswith("page:"))
async def page_turn_handler(call: CallbackQuery) -> None:
    _, lang, idx_str = call.data.split(":")
    current_idx = int(idx_str)
    user_id = call.from_user.id
    
    session = USER_SESSIONS.get(user_id)
    if not session:
        await call.answer("Session expired. Please restart with /start.", show_alert=True)
        return
        
    config = TRACKS_CONFIGS[lang]
    
    # Smooth modification overlay swap transition execution
    await call.message.edit_text(
        ANTHEM_LYRICS[lang][current_idx],
        reply_markup=get_pagination_kb(lang, current_idx, session["start_time"], config["duration"]),
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "check_timer")
async def check_timer_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    session = USER_SESSIONS.get(user_id)
    if not session:
        return
        
    lang = session["lang"]
    config = TRACKS_CONFIGS[lang]
    elapsed = time.time() - session["start_time"]
    
    if elapsed >= config["duration"]:
        # Timer has finished playing during interaction. Auto-unlock the frame.
        await call.message.edit_text(
            ANTHEM_LYRICS[lang][6],
            reply_markup=get_pagination_kb(lang, 6, session["start_time"], config["duration"]),
            parse_mode="HTML"
        )
        await call.answer("✨ Track Completed! Button Unlocked.")
    else:
        remaining = int(config["duration"] - elapsed)
        await call.answer(f"🔒 Keep absorbing the anthem. Only {remaining} seconds remaining.", show_alert=True)

@dp.callback_query(F.data == "confirm_completion")
async def confirm_completion_handler(call: CallbackQuery) -> None:
    user_id = call.from_user.id
    session = USER_SESSIONS.get(user_id)
    
    await call.answer("Verification Confirmed.")
    
    # REQUIREMENT 4: Clean slate background deletion routine
    if session:
        try:
            await bot.delete_message(chat_id=user_id, message_id=session["audio_msg_id"])
            await bot.delete_message(chat_id=user_id, message_id=session["lyrics_msg_id"])
        except Exception:
            pass # Failsafes to prevent background clutter crashes
            
        USER_SESSIONS.pop(user_id, None)
        
    # Launch threshold threshold gate into next phase
    await call.message.answer(
        "<b>Phase 2: Brief Introduction to Repellano Nigeria Limited (RNL)</b>\n\n"
        "Welcome to the second tier of the Sanctuary onboarding. Content loading...",
        parse_mode="HTML"
    )

async def handle_ping(request):
    return web.Response(text="Sanctuary Core Active", status=200)

async def main() -> None:
    app = web.Application()
    app.router.add_get("/", handle_ping)
