"""
Phase 3: Terms and Conditions (T&C) Management Router.
"""
from aiogram import Bot, Router, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import db
import rules_engine

router = Router()

TC_TEXT = (
    "📄 <b>Repellano Digital Sanctuary — Terms & Conditions</b>\n\n"
    "<b>Clause 7: Ownership and Funds Management</b>\n"
    "7(a) Every resource committed to trading within the RDS originates completely with RNL.\n"
    "7(b) A client may pause or temporarily step away from trading cycles under registered parameters.\n"
    "7(c) <i>If the Client walks away with the loan/gift (Repellano’s money), Repellano assumes "
    "the Client is not interested in advancing in the RDS. The Client may return later as described in (b).</i>\n\n"
    "🔒 <b>Foundational Rule Reminder:</b>\n"
    "No member can ever skip FSSO1 & FSSO2. Every member starts both sequentially.\n\n"
    "Please confirm your agreement by tapping the signature button below."
)

def get_tc_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ I Accept & Sign T&C", callback_data="tc:accept")]
    ])

async def start_tc_phase(bot: Bot, user_id: int, session: dict) -> None:
    """Invoked when a member successfully completes the portal handoff requirements."""
    msg = await bot.send_message(
        chat_id=user_id,
        text=TC_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=get_tc_keyboard()
    )
    session["phase"] = "terms"
    session["to_wipe"] = [msg.message_id]

@router.callback_query(F.data == "tc:accept")
async def on_accept_tc(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    # Record the digital signature acceptance securely to Neon Postgres
    if db.enabled():
        await db.log_event(user_id, "tc_signed", "Clause 7(c) acknowledged")
    
    await cb.answer("✅ Terms & Conditions signed successfully.", show_alert=True)
    # Trigger handoff to Phase 4 User Profiling (Next Step)
