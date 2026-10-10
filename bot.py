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

# NATIVE INLINE KEYBOARD: Links directly to your channel posts natively
def language_selection_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🎧 English Version (Play on @RDSTracks)", 
                url="https://t.me"
            )],
            [InlineKeyboardButton(
                text="🎧 Pidgin Version (Play on @RDSTracks)", 
                url="https://t.me"
            )]
        ]
    )

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Handles the onboarding introduction. Greets the user dynamically by name 
    and displays the persistent entry shield layout button.
    """
    user_name = message.from_user.first_name

    # Set up the persistent Menu Button to sit at the bottom next to the text input box
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(
            text="🛡️ Sanctuary Gate",
            web_app=WebAppInfo(url=BASE_URL)
        )
    )
    
    # Send the onboarding selection card directly inside Telegram's native chat layout
    await message.answer(
        f"<b>Welcome, Dear {user_name}</b>\n\n"
        "To begin, take your first step. Choose your language version below to listen to the Sanctuary's Anthem inside the channel.",
        reply_markup=language_selection_kb(),
        parse_mode="HTML"
    )

# --- LIGHTWEIGHT WEB COMPLIANCE FOR RUNNING CONTINUOUSLY ---
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
    
    # Start long polling service loops
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
