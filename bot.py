import asyncio
import os
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

# Secure Token Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAEe_3Hn-fQ-VHmcKMTdfXBIiC43b-lBGc0")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Your WebApp gateway URL hosted via Vercel
BASE_URL = "https://vercel.app"

# Source channel channel handling the stored target audios
CHANNEL_ID = "@RDSTracks"

# Language Version Keyboard Blueprint Configuration
def initial_language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎧 English Version", callback_data="play:en")],
            [InlineKeyboardButton(text="🎧 Pidgin Version", callback_data="play:pidgin")]
        ]
    )

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Handles onboarding entrance. Greets user dynamically by first name 
    and presents the persistent shield navigation menu bar.
    """
    user_name = message.from_user.first_name

    # Mount the persistent bottom menu button layout parameters
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(
            text="🛡️ Sanctuary Gate",
            web_app=WebAppInfo(url=BASE_URL)
        )
    )
    
    # EXACT COPY REQUIREMENT
    await message.answer(
        f"<b>Welcome, Dear {user_name}</b>\n\n"
        "To begin, take your first step. Click the menu button below",
        parse_mode="HTML"
    )
    
    # Prompt the functional selection payload right inside the chat window
    await message.answer(
        "Choose your language version to receive the Sanctuary's Anthem:",
        reply_markup=initial_language_kb()
    )

@dp.callback_query(F.data.startswith("play:"))
async def serve_anthem_callback(call: CallbackQuery) -> None:
    """
    Catches language selections, transfers the audio post file from channel 
    and prints out the full textual lyrics cleanly right underneath it.
    """
    lang_type = call.data.replace("play:", "")
    await call.answer("Accessing Sanctuary Core Assets...")

    # Assign correct source channel reference post indices
    # Post ID 6 maps to English track, Post ID 7 maps to Pidgin track
    target_msg_id = 6 if lang_type == "en" else 7

    try:
        # Copies the file smoothly into the user's private window chat layout
        await bot.copy_message(
            chat_id=call.from_user.id,
            from_chat_id=CHANNEL_ID,
            message_id=target_msg_id
        )
    except Exception as exc:
        await call.message.answer(f"⚠️ Could not pull media track file: {exc}\nEnsure the bot is added as an administrator inside the @RDSTracks channel.")
        return

    # Print out lyrics matching user language choice
    if lang_type == "en":
        lyrics_text = (
            "<b>📜 Repellano Anthem (English Lyrics)</b>\n\n"
            "<b>[Intro]</b>\n"
            "Welcome to the Sanctuary.\n"
            "Where the chaotic markets find their perfect peace.\n"
            "This is SemLeno's Repellano Digital Sanctuary.\n\n"
            "<b>[Verse 1]</b>\n"
            "The global markets spin in a wild, endless race\n"
            "Complex forex trading moving at a blinding pace\n"
            "But inside the Sanctuary, the vision is crystal clear\n"
            "We strip away the chaos, we break down the fear\n"
            "Turning heavy burdens into a simple tool for all.\n\n"
            "<b>[Chorus]</b>\n"
            "Simple. Automated. Universal.\n"
            "Thirty-five FSSOs, the tech reversal!\n"
            "Universal empowerment, no matter where you start\n"
            "Repellano lifting up every single heart!\n"
            "Every single heart! Every single heart! Every single heart!\n\n"
            "<b>[Verse 2]</b>\n"
            "An ecosystem built to redefine the grand design\n"
            "Where mathematics meets the market, aligning line by line\n"
            "A seamless architecture, steady, smooth, and deep\n"
            "Working in the silence while the world is fast asleep.\n\n"
            "<b>[Verse 3]</b>\n"
            "Thirty-five FSSOs standing structured and strong\n"
            "Financial Support Service Offerings where they belong\n"
            "Automated utilities that never tire or fade\n"
            "To help all those struggling with their finances\n\n"
            "<b>[Chorus]</b>\n"
            "Simple. Automated. Universal.\n"
            "Thirty-five FSSOs, the tech reversal!\n"
            "Universal empowerment, no matter where you start\n"
            "Repellano lifting up, up every single heart!\n"
            "Every single heart! Every single heart!\n\n"
            "<b>[Outro]</b>\n"
            "The Digital Sanctuary.\n"
            "We build, we automate, we rise.\n"
            "[Fade Out] [End]"
        )
    else:
        lyrics_text = (
            "<b>📜 Repellano Anthem (Pidgin Lyrics)</b>\n\n"
            "<b>[Intro]</b>\n"
            "Welcome to the Sanctuary.\n"
            "Where jagajaga forex markets find their perfect peace.\n"
            "This nah Semleno Repellano Digital Sanctuary.\n\n"
            "<b>[Verse 1]</b>\n"
            "The world market dey spin anyhow, e no dey stop\n"
            "Forex trading sharp well-well, things just dey pop\n"
            "But inside this Sanctuary, the vision clear pass glass\n"
            "We dey commot the confusion, make the fear join pass\n"
            "We dey change heavy load to, to simple tool for everybody.\n\n"
            "<b>[Chorus]</b>\n"
            "E simple. E dey run on own. E dey for everyone.\n"
            "Thirty-five FSSOs, the tech don change the run!\n"
            "Power dey for everybody, no matter where you start from\n"
            "Repellano oh, oh, oh every single heart up!\n"
            "Every single heart! Every single heart! Every single heart!\n\n"
            "<b>[Verse 2]</b>\n"
            "The whole setup dey here to change how things suppose to be\n"
            "Where math and market jam, things arrange properly\n"
            "The system solid well-well, e smooth and e deep\n"
            "E dey work sharp-sharp inside silence when the world dey sleep.\n\n"
            "<b>[Verse 3]</b>\n"
            "Thirty-five FSSOs stand gidigba, everything set well\n"
            "Financial Support Service Offerings, na him we call FSSOs\n"
            "Automated tools wey no dey tire or lose face\n"
            "To support everybody wey dey struggle hard to find small money\n\n"
            "<b>[Chorus]</b>\n"
            "Simple. Automated. Universal.\n"
            "Thirty-five FSSOs, the tech reversal!\n"
            "Financial power for you, no matter where you start\n"
            "Repellano oh, oh, oh every single heart up!\n"
            "Every single heart! Every single heart! Every single heart!\n\n"
            "<b>[Outro]</b>\n"
            "The Digital Sanctuary.\n"
            "We don build, we don automate, we wan rise.\n"
            "[Fade Out] [End]"
        )

    await call.message.answer(lyrics_text, parse_mode="HTML")

# --- WEB SERVER COUPLING ---
async def handle_ping(request):
    return web.Response(text="Sanctuary Core Active", status=200)

async def main() -> None:
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
