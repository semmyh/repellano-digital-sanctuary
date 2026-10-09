import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, MenuButtonWebApp, WebAppInfo
from aiohttp import web

# Secure Token Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAEe_3Hn-fQ-VHmcKMTdfXBIiC43b-lBGc0")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Your WebApp gateway URL (We will host the overlay here via Vercel in Phase 2)
BASE_URL = "https://vercel.app"

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    Handles the onboarding introduction. Sets up the persistent
    Menu Button with the shield hook requirements.
    """
    # Enforces the persistent text and link interface directly inside Telegram's UI
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(
            text="🛡️ Click to Enter the Sanctuary",
            web_app=WebAppInfo(url=BASE_URL)
        )
    )
    
    await message.answer(
        "<b>The Repellano Digital Sanctuary Activated</b>\n\n"
        "To begin the Anthem Onboarding Framework (AOF), click the <b>🛡️ Click to Enter the Sanctuary</b> menu button below next to your keyboard text field.",
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
