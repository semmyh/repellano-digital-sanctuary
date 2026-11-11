"""
RDS General Rules & Limitations: backend rules engine.
Pure functions only (no Telegram, no database), so every rule can be tested in
isolation and called from any handler before a member reaches the next phase.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

LAGOS = ZoneInfo("Africa/Lagos")

MIN_AGE = 20
TOTAL_FSSOS = 35
COMPULSORY = (1, 2)
SUBSEQUENT_CAPITAL_RATIO = Decimal("0.5")
RENEWAL_REST_DAYS = 14
FREE_FSSO1_DELETION_DAYS = 30

@dataclass(frozen=True)
class Tier:
    name: str
    max_simultaneous: int
    max_guarantees: int
    can_be_banished: bool
    fine_range_ngn: tuple[int, int] | None
    application_fee_ngn: int = 0

MAX_DISTINCT_UNLESS_UPGRADED = 3
MAX_TRADE_CYCLES = 3

TIERS: dict[str, Tier] = {
    "lead": Tier("Registered Lead", 1, 0, False, None),
    "paid": Tier("Paid Client / Lead", 3, 4, True, None),
    "vip": Tier("VIP", 4, 6, False, None, 250000),
    "resident": Tier("Repellano Resident", 5, 8, False, (2000000, 3000000), 1000000),
    "citizen": Tier("Repellano Citizen", 6, 10, False, (3500000, 5000000), 3000000),
}

FSSO1_FUNDING_DEADLINE_HOURS = 1
FSSO1_RESTRICTION_MONTHS = 6

def funding_deadline(loan_sent_at: datetime) -> datetime:
    return loan_sent_at + timedelta(hours=FSSO1_FUNDING_DEADLINE_HOURS)

def funding_timed_out(loan_sent_at: datetime, funded_at: datetime | None, now: datetime) -> bool:
    deadline = funding_deadline(loan_sent_at)
    return (funded_at > deadline) if funded_at is not None else (now > deadline)

def is_funded(fsso_no: int, linked_account_balance_usd) -> bool:
    minimum = FSSO_SCHEDULE[fsso_no].slave_min_usd
    return minimum is not None and Decimal(str(linked_account_balance_usd)) >= Decimal(str(minimum))

def trading_may_commence(master_balance_usd, linked_account_balance_usd) -> bool:
    return Decimal(str(master_balance_usd)) <= Decimal(str(linked_account_balance_usd))

@dataclass(frozen=True)
class FssoInfo:
    name: str
    category: str
    admin_fee_ngn: int
    renewal_fee_ngn: int | None
    duration_days: int | None
    master_min_usd: int | None
    slave_min_usd: int | None
    equity_target_usd: int | None
    rnl_share_usd: int | None
    member_share_usd: int | None
    exits_rds: bool
    lifetime_ownership: bool

    @property
    def is_lifetime(self) -> bool:
        return self.duration_days is None

FSSO_SCHEDULE: dict[int, FssoInfo] = {
    1: FssoInfo('Starter Trader Fund', 'Core Financial Foundation', 50000, None, None, 10, 10, 375, 150, 150, False, False),
    2: FssoInfo('Rainy Day Fund', 'Core Financial Foundation', 50000, 30000, 730, 50, 50, 1600, 750, 750, False, False), # 2 years, Renewable
    25: FssoInfo('Our New Baby Fund', 'Life Milestones', 50000, 30000, 730, 50, 100, 2200, 1000, 1000, False, False),
    33: FssoInfo('My Prop Funded Dream', 'Last Destination', 5000000, None, None, None, None, None, None, None, True, True),
    34: FssoInfo('My FX Trader Bot', 'Last Destination', 5500000, None, None, None, None, None, None, None, True, True),
    35: FssoInfo('Last Destination', 'High-Level FX Trading', 2000000, None, None, 50, 4500, 57000, 25000, 25000, True, False),
}

def check_fsso_access(fsso_no: int, tier_key: str, completed: set[int], active: set[int], 
                      user_gender: str = "unknown", user_age: int = 0, FSSO25_history: list = None) -> tuple[bool, str]:
    if not 1 <= fsso_no <= TOTAL_FSSOS:
        return False, "That FSSO does not exist."
    if tier_key == "lead" and fsso_no != 1:
        return False, "Registered leads can only use FSSO1. Upgrade to Paid first."
    if fsso_no in active:
        return False, "This FSSO is already activated; duplicate cycles are not allowed."
    if fsso_no == 1 and 1 in completed:
        return False, "Compulsory FSSO1 can only be taken once in a lifetime."

    if fsso_no == 1:
        if active:
            return False, "FSSO1 and FSSO2 must run sequentially, never together."
        return True, "OK"

    if fsso_no == 2:
        if 1 not in completed:
            return False, "Complete FSSO1 before FSSO2."
        if active:
            return False, "FSSO1 and FSSO2 must run sequentially, never together."
        return True, "OK"

    if 2 not in completed:
        return False, "Complete foundational FSSO2 before unlocking other pipelines."
        
    if fsso_no == 25:
        if user_gender.lower() != "female":
            return False, "FSSO25 allocation is strictly limited to female members."
        if user_age < 20:
            return False, "FSSO25 requires a minimum profile metric of 20 years of age."
        if FSSO25_history and len(FSSO25_history) >= 2:
            return False, "FSSO25 is strictly capped at a lifetime maximum of 2 births."
        if FSSO25_history:
            last_birth_date = max(FSSO25_history)
            if (date.today() - last_birth_date).days < 730:
                return False, "FSSO25 requires a minimum 2-year spacing interval between birth events."

    tier = TIERS[tier_key]
    if len(active) >= tier.max_simultaneous:
        return False, f"Your tier ({tier.name}) allows {tier.max_simultaneous} FSSOs activated at a time."
    return True, "OK"

# --- GUARANTOR INVARIANTS ---
GUARANTOR_MIN_AGE = 25
GUARANTOR_CATEGORIES = ("rds_member", "spouse", "parent", "uncle_cousin_or_nephew")

def guarantor_eligible(category: str, age: int, telegram_age_months: float) -> tuple[bool, str]:
    if category not in GUARANTOR_CATEGORIES:
        return False, "Guarantor classification out of compliance profiles."
    if age < GUARANTOR_MIN_AGE:
        return False, f"Guarantor profiles must satisfy the minimum age of {GUARANTOR_MIN_AGE}."
    if telegram_age_months < 6.0:
        return False, "Target Telegram account must possess a verified footprint age of at least 180 days."
    return True, "OK"
