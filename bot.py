import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("repellano")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8642428323:AAHO71GubQl4kvAIeT1dpI_NA2gsqKGS8eI").strip()

# --- STEP 1 TEXT LAYOUT (Forced Markdown Mode) ---
# Wrapping a variable in asterisks (*) makes it completely bold in standard Markdown.
GREETING = (
    "Welcome, Dear *{name}*\!\n\n"
    "To begin, take the first step\. Choose your language version "
    "below to enjoy the Sanctuary's Anthem\."
)

USER_SESSIONS: dict[int, dict] = {}

# Globally configure the bot engine instance to read standard Markdown format properties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
dp = Dispatcher()

# --- STEP 1 LAYOUT KEYBOARD ---
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 English Version", callback_data="lang:en")],
        [InlineKeyboardButton(text="🎧 Pidgin Version",  callback_data="lang:pidgin")],
    ])

# --- /start COMMAND ROUTE ---
@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id
    name = message.from_user.first_name or "Leno"

    # Isolate user mapping parameters to support Step 5 multiple concurrent runs
    session = {"lang": None, "to_wipe": [], "task": None, "remaining": 0}
    USER_SESSIONS[user_id] = session

    # Post greeting explicitly with Markdown rules enforced
    greeting = await message.answer(
        text=GREETING.format(name=name),
        reply_markup=lang_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    session["to_wipe"].append(greeting.message_id)

# --- WEB STATUS SERVER ROUTINES ---
async def health(_: web.Request) -> web.Response:
    return web.Response(text="Status: Active.")

async def start_web() -> None:
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    await web.TCPSite(runner, "0.0.0.0", port).start()

# --- EXECUTION SYSTEM ---
async def main() -> None:
    await start_web()
    log.info("Starting up service polling...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    # CRITICAL ARCHITECTURAL FIX: Pass 'bot' object here to stop the 'Dispatcher' crash completely
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Server terminated cleanly.")
