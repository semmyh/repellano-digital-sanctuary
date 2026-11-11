"""
Phase 4: User Profiling and KYC Verification Engine.
Handles biographical metadata capture, dynamic age calculations, 
gender tracking, and strict 25+ relational guarantor pings.
"""
from datetime import date
import logging
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ParseMode

import db
import rules_engine

log = logging.getLogger("repellano.profiling")
router = Router()

class ProfilingStates(StatesGroup):
    waiting_for_full_name = State()
    waiting_for_birth_date = State()
    waiting_for_gender = State()
    waiting_for_guarantor_type = State()
    waiting_for_guarantor_age = State()
    waiting_for_guarantor_telegram_age = State()

def gender_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Female"), KeyboardButton(text="Male")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def guarantor_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="RDS Member"), KeyboardButton(text="Spouse")],
            [KeyboardButton(text="Parent"), KeyboardButton(text="Uncle / Cousin / Nephew")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

async def start_profiling_flow(message: Message, state: FSMContext):
    """Entry point triggered immediately following the successful validation of Phase 3 T&C signing."""
    await state.set_state(ProfilingStates.waiting_for_full_name)
    await message.answer(
        "📝 <b>Phase 4: User Profiling & KYC Verification</b>\n\n"
        "Let's establish your professional identity profile.\n"
        "Please enter your <b>Full Legal Name</b> exactly as it appears on your official documents:",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(ProfilingStates.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    name_text = message.text.strip()
    if len(name_text) < 3 or not all(x.isalpha() or x.isspace() for x in name_text):
        await message.answer("⚠️ Please enter a valid legal name (letters and spaces only):")
        return
    
    await state.update_data(full_name=name_text)
    await state.set_state(ProfilingStates.waiting_for_birth_date)
    await message.answer(
        "📅 Please enter your date of birth in <b>YYYY-MM-DD</b> format (e.g., 1995-08-24):",
        parse_mode=ParseMode.HTML
    )

@router.message(ProfilingStates.waiting_for_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    try:
        birth_date = date.fromisoformat(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Invalid format. Please utilize the strict format: <b>YYYY-MM-DD</b>:", parse_mode=ParseMode.HTML)
        return

    # Calculate precise age profile against Lagos baseline
    today = rules_engine.today_lagos()
    user_age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    if user_age < rules_engine.MIN_AGE:
        await state.clear()
        # Direct enforcement of the non-waivable Lead Profiling disqualification barrier
        await message.answer(
            f"❌ <b>Disqualification Notice:</b>\n"
            f"Your registered age profile is {user_age}. You must be at least {rules_engine.MIN_AGE} years old to participate in the RDS.\n"
            f"<i>There is no waiver privilege for this baseline restriction.</i>",
            parse_mode=ParseMode.HTML
        )
        return

    await state.update_data(birth_date=birth_date.isoformat(), age=user_age)
    await state.set_state(ProfilingStates.waiting_for_gender)
    await message.answer(
        "👤 Please select your biological gender metrics below:",
        reply_markup=gender_keyboard()
    )

@router.message(ProfilingStates.waiting_for_gender, F.text.in_(["Female", "Male"]))
async def process_gender(message: Message, state: FSMContext):
    await state.update_data(gender=message.text)
    await state.set_state(ProfilingStates.waiting_for_guarantor_type)
    await message.answer(
        "🛡️ <b>Guarantor Prequalification Setup</b>\n\n"
        "To back your initial funding routes, select your chosen guarantor profile classification:",
        parse_mode=ParseMode.HTML,
        reply_markup=guarantor_type_keyboard()
    )

@router.message(ProfilingStates.waiting_for_guarantor_type)
async def process_guarantor_type(message: Message, state: FSMContext):
    g_type = message.text.strip()
    mapping = {
        "RDS Member": "rds_member",
        "Spouse": "spouse",
        "Parent": "parent",
        "Uncle / Cousin / Nephew": "uncle_cousin_or_nephew"
    }
    
    if g_type not in mapping:
        await message.answer("⚠️ Out of compliance selection. Please utilize the provided keyboard options:")
        return

    await state.update_data(guarantor_category=mapping[g_type])
    await state.set_state(ProfilingStates.waiting_for_guarantor_age)
    await message.answer(
        "🎂 Enter your designated guarantor's current <b>Age</b> (Minimum requirement: 25):",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(ProfilingStates.waiting_for_guarantor_age)
async def process_guarantor_age(message: Message, state: FSMContext):
    try:
        g_age = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Please provide a valid numerical age:")
        return

    if g_age < rules_engine.GUARANTEE_MIN_AGE:
        await message.answer(f"❌ Structural violation: Guarantor must be at least {rules_engine.GUARANTEE_MIN_AGE} years of age. Provide a compliant guarantor:")
        return

    await state.update_data(guarantor_age=g_age)
    await state.set_state(ProfilingStates.waiting_for_guarantor_telegram_age)
    await message.answer(
        "⏳ For how many <b>months</b> has this guarantor possessed an active Telegram account footprint? (Minimum requirement: 6 months):",
        parse_mode=ParseMode.HTML
    )

@router.message(ProfilingStates.waiting_for_guarantor_telegram_age)
async def process_guarantor_telegram_age(message: Message, state: FSMContext):
    try:
        tg_age = float(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Please provide a valid numerical month value:")
        return

    data = await state.get_data()
    
    # Run absolute behavioral evaluation metrics against rules engine
    eligible, reason = rules_engine.guarantor_eligible(
        category=data["guarantor_category"],
        age=data["guarantor_age"],
        telegram_age_months=tg_age
    )

    if not eligible:
        await message.answer(f"❌ <b>Guarantor Rejected:</b>\n{reason}\nPlease input a different profile to proceed.", parse_mode=ParseMode.HTML)
        await state.set_state(ProfilingStates.waiting_for_guarantor_type)
        await message.answer("Select your chosen guarantor profile classification:", reply_markup=guarantor_type_keyboard())
        return

    user_id = message.from_user.id
    
    # Commit profile directly to Neon database persistence layers
    if db.enabled():
        await db.upsert_member(user_id, data["full_name"])
        await db.log_event(user_id, "profiling_complete", f"Gender: {data['gender']}, Age: {data['age']}")

    await state.clear()
    await message.answer(
        "🎉 <b>Profile Verification Absolute Success!</b>\n\n"
        "Your legal identities, profile matrix configurations, and guarantor parameters have passed all architectural sanity filters.\n"
        "You are now prequalified and fully unlocked to initialize <b>Phase 5: FSSO Allocation selection</b>.",
        parse_mode=ParseMode.HTML
    )
