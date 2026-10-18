import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("repellano")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAHO71GubQl4kvAIeT1dpI_NA2gsqKGS8eI").strip()

# --- CONFIGURATION FOR STEP 1 ---
# This exact layout matches your concept criteria. Note the "Dear {name}" correction!
GREETING = (
    "Welcome, Dear <b>{name}</b>!\n\n"
    "To begin, take the first step. Choose your language version "
    "below to enjoy the Sanctuary's Anthem."
)

USER_SESSIONS: dict[int, dict] = {}

# CRITICAL FIX: We declare the Default HTML parse mode explicitly inside the bot constructor properties.
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- KEYBOARD FOR STEP 1 ---
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version",  callback_data="lang:pidgin")],
    ])

# --- /start COMMAND TRIGGER ---
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    name = message.from_user.first_name or "Leno"

    # Initialize user session storage cleanly
    session = {"lang": None, "to_wipe": [], "task": None, "remaining": 0}
    USER_SESSIONS[user_id] = session

    # Send the greeting message using the forced HTML parameters
    greeting = await message.answer(
        text=GREETING.format(name=name),
        reply_markup=lang_keyboard()
    )
    
    # Store this ID so we can wipe it later in Step 4
    session["to_wipe"].append(greeting.message_id)

# --- MINIMAL HEALTH SERVER FOR RENDER ---
async def health(_: web.Request) -> web.Response:
    return web.Response(text="Step 1 Server Alive.")

async def start_web() -> None:
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    await web.TCPSite(runner, "0.0.0.0", port).start()

async def main() -> None:
    await start_web()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(dp)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
