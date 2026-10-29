"""
Phase 3: General Rules and Limitations.

A paged card walkthrough shown in the chat right after the member finishes the six sections of
the Corporate Portal (file kept as phase2.py so existing imports keep working).
- One message per member; Back / Next EDIT that message (user-driven, no timers).
- Page content lives in PAGES, so wording can change without touching the logic.
- Each member has a private session; nothing is shared between users.

Pages marked REVIEW contain wording that should go through legal review before launch.
"""
import time
import logging

from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import asyncio

log = logging.getLogger("repellano.phase2")
router = Router(name="phase2")

_sessions: dict = {}


def init(sessions: dict) -> None:
    """Share the bot's per-user session store with this module."""
    global _sessions
    _sessions = sessions


# --- CONTENT (HTML parse mode) ---
TITLE = "📜 <b>Phase 3: General Rules and Limitations</b>"

PAGES: list[str] = [
    # 1. Introduction
    f"{TITLE}\n\n"
    "Before you begin, please read the rules that apply across the whole <b>Repellano Digital "
    "Sanctuary (RDS)</b>. The RDS offers <b>35 Financial Support Service Offerings (FSSOs)</b>, "
    "and these rules apply to all of them.\n\n"
    "Tap <b>Next</b> to continue.",

    # 3. Who can join
    "🪪 <b>Who can join</b>\n\n"
    "• You must be at least <b>20 years old</b>. Some FSSOs need a higher age, and you "
    "must be pre-qualified for it first.\n"
    "• No RDS member is involved in drugs, drunkenness, violence or prostitution. "
    "A member found otherwise risks a lifetime ban.\n"
    "• Your chosen <b>Guarantor</b> must vouch for this character to Repellano.",

    # 4. Your journey
    "🛤 <b>Your journey</b>\n\n"
    "You can <b>see</b> every FSSO, but you unlock them in order.\n\n"
    "1️⃣ <b>FSSO1 (Starter Loan):</b> every new lead receives a $10 trading cash loan. "
    "If the first trade is a LOSS, the loan is given again for the next cycle. This repeats "
    "until a trade is a WIN, which permanently ends the starter loan. No other FSSO offers it.\n"
    "2️⃣ <b>FSSO2:</b> opens after FSSO1.\n\n"
    "FSSO1 and FSSO2 are compulsory, run one after the other (never together), and each can "
    "be taken only once in a lifetime. Complete FSSO2 to unlock the rest.\n\n"
    "A free FSSO1 account is deleted after 30 days if the $10 security deposit is not paid.\n\n"
    "⏱ <b>One-hour rule:</b> after RNL sends you the $10 loan, you must fund your trading account "
    "within <b>one hour</b>. If you do not, you are restricted from the RDS for <b>6 months</b> and "
    "your $10 security deposit goes to RNL as repayment of the $10 loan. You keep the $10 loan in "
    "return for the deposit.",

    # 5. Money rules  (REVIEW: legal)
    "💼 <b>How the money rules work</b>\n\n"
    "• By default, the company covers trading losses.\n"
    "• The profit share paid to you from any FSSO is treated as a gifted <b>cash loan</b> "
    "from RNL. You may invest it in other FSSOs to grow it, or walk away with it.\n"
    "• If you walk away and return later, you are reminded of the total gifted cash loan you "
    "hold, and you may invest it in any FSSO.\n"
    "• After FSSO1, the capital for a new FSSO is capped at 50% of the profit shares from your "
    "previous WON cycles.\n"
    "• If cycle 1 is a LOSS (all FSSOs except FSSO1), you may run cycle 2 or walk away.\n"
    "• Each time you launch a new FSSO, you receive a report of your net cumulative cash loan "
    "gift to date.",

    # 6. Calendar and accounts
    "📅 <b>Funding, accounts and calendar</b>\n\n"
    "• Every FSSO has its own dedicated MT4 or MT5 trading account.\n"
    "• You cannot link the same account to two FSSOs activated at the same time.\n"
    "• To start a new FSSO, fund its account during the <b>last 7 days of a month</b>. Trading "
    "starts on the <b>first working day of the next month</b>.\n"
    "• If an activated FSSO has a LOSS, funding for the new trade cycle opens "
    "<b>immediately</b>, and trading begins on the <b>first trading day of the next week</b>.\n"
    "• Each FSSO has its own locked <b>duration</b>. It starts only after your final equity target "
    "is reached and every payout is made, and it never extends. After it ends, there is a "
    "<b>2-week compulsory pause</b> before the FSSO can be renewed. Lifetime FSSOs can be "
    "activated only once.",

    # 7. Tiers
    "🏅 <b>Membership tiers</b>\n\n"
    "No member may take two of the same FSSO at once, or more than 3 different FSSOs at once, "
    "unless they are a VIP, Resident or Citizen.\n\n"
    "• <b>Registered Lead:</b> FSSO1 only, free for 30 days, then upgrade to Paid\n"
    "• <b>Paid Client:</b> 3 FSSOs activated at once, 4 guarantees\n"
    "• <b>VIP (₦250,000):</b> 4 FSSOs, 6 guarantees\n"
    "• <b>Resident (₦1,000,000):</b> 5 FSSOs, 8 guarantees\n"
    "• <b>Citizen (₦3,000,000):</b> 6 FSSOs, 10 guarantees",

    # 8. Breaches and fines
    "⚖️ <b>Rule breaches and fines</b>\n\n"
    "• <b>Paid Client:</b> can be banished for infractions, breach of the Terms, or reputational "
    "damage caused by a guarantee's infraction.\n"
    "• <b>VIP:</b> cannot be banished, but a serious breach returns you to Paid Client without a "
    "refund of the application fee.\n"
    "• <b>Resident:</b> cannot be banished, but can be restricted or fined ₦2,000,000 to ₦3,000,000.\n"
    "• <b>Citizen:</b> cannot be banished, but can be restricted or fined ₦3,500,000 to ₦5,000,000.\n\n"
    "Residents and Citizens may sell guarantees at ₦50,000 each, at the risk of reputational "
    "damage caused by the guarantee.\n\n"
    "When a Resident or Citizen is fined, their RDS access is frozen until Korapay confirms the "
    "payment. You are then notified and access is restored.",
]

LAST = len(PAGES) - 1


# --- KEYBOARDS ---
def keyboard(page: int) -> InlineKeyboardMarkup:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="◀️ Back", callback_data="p2:back"))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{len(PAGES)}", callback_data="p2:noop"))
    if page < LAST:
        row.append(InlineKeyboardButton(text="Next ▶️", callback_data="p2:next"))
    rows = [row]
    if page == LAST:
        rows.append([InlineKeyboardButton(text="✅ I Have Read and Understood", callback_data="p2:ack")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- ENTRY POINT (called by bot.py right after the clean sweep) ---
async def start(bot: Bot, user_id: int, session: dict) -> None:
    msg = await bot.send_message(
        chat_id=user_id,
        text=PAGES[0],
        reply_markup=keyboard(0),
        parse_mode=ParseMode.HTML,
    )
    session["phase"] = "phase2"
    session["p2_page"] = 0
    session["p2_msg"] = msg.message_id
    session["to_wipe"] = [msg.message_id]  # so a later /start can wipe it


async def _edit(cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None) -> bool:
    for _ in range(2):
        try:
            await cb.message.edit_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramBadRequest as e:
            log.info("Phase 3 edit skipped: %s", e)
            return False
    return False


def _active_session(cb: CallbackQuery) -> dict | None:
    session = _sessions.get(cb.from_user.id)
    if session and session.get("phase") == "phase2":
        return session
    return None


# --- HANDLERS ---
@router.callback_query(F.data == "p2:noop")
async def on_noop(cb: CallbackQuery) -> None:
    await cb.answer()


@router.callback_query(F.data.in_({"p2:next", "p2:back"}))
async def on_nav(cb: CallbackQuery) -> None:
    session = _active_session(cb)
    if session is None:
        await cb.answer("Session expired. Please type /start to begin.", show_alert=True)
        return

    delta = 1 if cb.data == "p2:next" else -1
    page = max(0, min(LAST, session["p2_page"] + delta))
    if page == session["p2_page"]:
        await cb.answer()
        return

    await cb.answer()
    if await _edit(cb, PAGES[page], keyboard(page)):
        session["p2_page"] = page


@router.callback_query(F.data == "p2:ack")
async def on_ack(cb: CallbackQuery) -> None:
    session = _active_session(cb)
    if session is None:
        await cb.answer("Session expired. Please type /start to begin.", show_alert=True)
        return
    if session["p2_page"] != LAST:
        await cb.answer("Please read to the last page first.", show_alert=True)
        return

    session["phase"] = "acknowledging"  # blocks double taps
    await cb.answer()
    session["p2_ack_at"] = time.time()  # log the acknowledgement timestamp for the backend
    log.info("User %s acknowledged Phase 3 at %s", cb.from_user.id, session["p2_ack_at"])

    await _edit(
        cb,
        "✅ <b>Phase 3 complete.</b>\nThank you for reading the Sanctuary's general rules.\n\n"
        "Your next step, getting started with FSSO1, is coming soon.",
        None,
    )
    session["phase"] = "done"
