# -*- coding: utf-8 -*-
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
    "vip": Tier("VIP", 4, 6, False, None, 250_000),                           
    "resident": Tier("Repellano Resident", 5, 8, False, (2_000_000, 3_000_000), 1_000_000),
    "citizen": Tier("Repellano Citizen", 6, 10, False, (3_500_000, 5_000_000), 3_000_000),
}

FSSO1_FUNDING_DEADLINE_HOURS = 1     
FSSO1_RESTRICTION_MONTHS = 6         

FSSO1_FUNDING_WARNING = (
    "Before you place your $10 security deposit, please note: once RNL sends you the $10 loan, "
    "you must fund your trading account within one hour. If you do not, you will be restricted "
    "from the RDS for 6 months and your $10 security deposit will go to RNL as repayment of the "
    "$10 loan. You then keep the $10 loan in return for your deposit."
)
FSSO1_TIMEOUT_NOTICE = (
    "You did not fund your trading account within one hour of receiving the $10 loan. As explained "
    "before you placed your deposit, you are restricted from the RDS for the next 6 months, and your "
    "$10 security deposit goes to RNL as repayment of the loan. Please keep the $10 loan as a return "
    "of your security deposit."
)

def funding_deadline(loan_sent_at: datetime) -> datetime:
    return loan_sent_at + timedelta(hours=FSSO1_FUNDING_DEADLINE_HOURS)

def funding_timed_out(loan_sent_at: datetime, funded_at: datetime | None, now: datetime) -> bool:
    deadline = funding_deadline(loan_sent_at)
    return (funded_at > deadline) if funded_at is not None else (now > deadline)

def is_funded(fsso_no: int, linked_account_balance_usd) -> bool:
    minimum = FSSO_SCHEDULE[fsso_no].slave_min_usd
    return minimum is not None and _money(linked_account_balance_usd) >= _money(minimum)

def trading_may_commence(master_balance_usd, linked_account_balance_usd) -> bool:
    return _money(master_balance_usd) <= _money(linked_account_balance_usd)

def add_months(start: datetime, months: int) -> datetime:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    last_day = (date(year + (month // 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return start.replace(year=year, month=month, day=min(start.day, last_day))

def restriction_end(start: datetime) -> datetime:
    return add_months(start, FSSO1_RESTRICTION_MONTHS)

REMITTANCE_DEADLINE_HOURS = 1        
REMITTANCE_GRACE_HOURS = 1           

def remittance_consequence(tier_key: str) -> str:
    return {
        "paid": "lifetime_ban",
        "vip": "strip_to_paid",
        "resident": "restrict_and_fine",
        "citizen": "restrict_and_fine",
    }[tier_key]

def upgrade_allowed(target_tier: str, lifetime_loan_gift_usd, ngn_per_usd) -> bool:
    fee_ngn = TIERS[target_tier].application_fee_ngn
    if not fee_ngn:
        return False
    fee_usd = Decimal(fee_ngn) / Decimal(str(ngn_per_usd))
    return Decimal(str(lifetime_loan_gift_usd)) >= fee_usd * 2

def remittance_status(requested_at: datetime, paid_at: datetime | None, now: datetime,
                      waived_at: datetime | None = None) -> str:
    deadline = requested_at + timedelta(hours=REMITTANCE_DEADLINE_HOURS)
    if paid_at is not None and paid_at <= deadline:
        return "on_time"
    if waived_at is None:
        return "pending" if (paid_at is None and now <= deadline) else "late_ban_due"
    grace_end = waived_at + timedelta(hours=REMITTANCE_GRACE_HOURS)
    if paid_at is not None and paid_at <= grace_end:
        return "paid_after_waiver"
    return "pending_after_waiver" if now <= grace_end else "permanent_ban_due"

STARTER_LOAN_USD = 10          
SECURITY_DEPOSIT_USD = 10      

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
    age_limit: int                   
    age_waivable: bool               
    proof_required: bool             
    proof_document: str | None       

    @property
    def is_lifetime(self) -> bool:
        return self.duration_days is None

    @property
    def fet_remainder_usd(self) -> int | None:
        if None in (self.equity_target_usd, self.rnl_share_usd, self.member_share_usd):
            return None
        return self.equity_target_usd - self.rnl_share_usd - self.member_share_usd

FSSO_SCHEDULE: dict[int, FssoInfo] = {
    1: FssoInfo('Starter Trader Fund', 'Core Financial Foundation', 50000, None, None, 10, 10, 375, 150, 150, False, False, 20, False, False, None),
    2: FssoInfo('Rainy Day Fund', 'Core Financial Foundation', 50000, 30000, 730, 50, 50, 1600, 750, 750, False, False, 20, False, False, None), 
    3: FssoInfo('My Daily Meal', 'Living Essentials', 50000, 30000, 90, 50, 50, 1150, 500, 500, False, False, 20, False, False, None),
    4: FssoInfo('My Annual Rent', 'Living Essentials', 50000, 30000, 365, 50, 50, 1600, 750, 750, False, False, 25, False, False, None),
    5: FssoInfo('My Annual Clothing', 'Living Essentials', 50000, 30000, 365, 50, 50, 1150, 500, 500, False, False, 20, False, False, None),
    6: FssoInfo('My Health Insurance', 'Living Essentials', 50000, 30000, 365, 50, 50, 1600, 750, 750, False, False, 20, False, False, None),
    7: FssoInfo('My New Phone', 'Lifestyle, Bills & Comfort', 50000, 30000, 1460, 50, 50, 900, 375, 375, False, False, 20, False, False, None),
    8: FssoInfo('My Monthly Bills', 'Lifestyle, Bills & Comfort', 50000, 30000, 90, 50, 50, 900, 375, 250, False, False, 20, False, False, None),
    9: FssoInfo('My Weekend Pepper soup', 'Lifestyle, Bills & Comfort', 50000, 30000, 90, 50, 50, 900, 375, 250, False, False, 20, False, False, None),
    10: FssoInfo('My Vacation Fund', 'Lifestyle, Bills & Comfort', 50000, 30000, 365, 50, 50, 1600, 750, 750, False, False, 23, False, False, None),
    11: FssoInfo('My Cancer Medics Fund', 'Intensive Medicare', 50000, 30000, 90, 50, 100, 2200, 1000, 1000, False, False, 23, True, True, 'Medical'),
    12: FssoInfo('My Dialysis Fund', 'Intensive Medicare', 50000, 30000, 60, 50, 100, 3200, 1500, 1500, False, False, 20, True, True, 'Medical'),
    13: FssoInfo('My Surgery Fund', 'Intensive Medicare', 50000, 30000, 365, 50, 100, 2200, 1000, 1000, False, False, 23, True, True, 'Medical'),
    14: FssoInfo('My IVF Fund', 'Intensive Medicare', 50000, 30000, 730, 50, 100, 3200, 1500, 1500, False, False, 23, True, True, 'Medical'),
    15: FssoInfo('My Point-of-Sale Biz', 'Micro Businesses & Hustles', 50000, 30000, 1095, 50, 50, 1600, 750, 750, False, False, 20, False, False, None),
    16: FssoInfo('My Mini Importation Biz', 'Micro Businesses & Hustles', 50000, 30000, 1095, 50, 100, 3200, 1500, 1500, False, False, 20, False, False, None),
    17: FssoInfo('I Work with My Hands', 'Micro Businesses & Hustles', 50000, 30000, 1095, 50, 100, 2200, 1000, 1000, False, False, 20, False, False, None),
    18: FssoInfo('My Starter Farm Biz', 'Micro Businesses & Hustles', 50000, 30000, 1095, 50, 100, 3200, 1500, 1500, False, False, 20, False, False, None),
    19: FssoInfo('My Ice Block Biz', 'Micro Businesses & Hustles', 50000, 30000, 1095, 50, 100, 2200, 1000, 1000, False, False, 20, False, True, 'Invoice from Approved Vendor'),
    20: FssoInfo('My Party Rentals Biz', 'Micro Businesses & Hustles', 50000, 30000, 1095, 50, 100, 2200, 1000, 1000, False, False, 25, False, False, None),
    21: FssoInfo('Buy & Sell Biz (Market Trader)', 'Micro Businesses & Hustles', 50000, 30000, 1095, 50, 100, 2200, 1000, 1000, False, False, 20, False, False, None),
    22: FssoInfo('My Tractor Rider Biz', 'Micro Businesses & Hustles', 500000, 200000, 1095, 50, 1500, 12200, 5000, 5000, False, False, 28, False, False, None),
    23: FssoInfo('My School Fees', 'Life Milestones', 50000, 30000, 365, 50, 100, 2200, 1000, 1000, False, False, 20, False, True, 'Admission Letter'),
    24: FssoInfo('Our Wedding Expenses', 'Life Milestones', 50000, None, None, 50, 100, 3200, 1500, 1500, False, False, 23, False, True, 'Marriage Certificate'),
    25: FssoInfo('Our New Baby Fund', 'Life Milestones', 50000, 30000, 730, 50, 100, 2200, 1000, 1000, False, False, 23, False, True, 'Birth Certificate'),
    26: FssoInfo('My Pension Booster', 'Life Milestones', 50000, None, None, 50, 1000, 10200, 4500, 4500, False, False, 30, False, True, 'Pension Certificate'),
    27: FssoInfo('My Japa Dream', 'Life Milestones', 50000, 30000, 1095, 50, 100, 2200, 1000, 1000, False, False, 20, False, False, None),
    28: FssoInfo('My Plot of Land', 'Land Assets & Infrastructure', 250000, None, None, 50, 500, 5750, 2500, 2500, False, False, 20, False, True, 'Land Purchase Proof'),
    29: FssoInfo('Secure My Land', 'Land Assets & Infrastructure', 250000, None, None, 50, 500, 5750, 2500, 2500, False, False, 20, False, True, 'Land Purchase Proof'),
    30: FssoInfo('Build My Shelter', 'Land Assets & Infrastructure', 250000, None, None, 50, 1000, 11500, 5000, 5000, False, False, 20, False, True, 'Land Purchase Proof'),
    31: FssoInfo('My Solar Power Fund', 'Land Assets & Infrastructure', 250000, 30000, 1460, 50, 500, 5750, 2500, 2500, False, False, 20, False, False, 'Invoice from Approved Vendor'),
    32: FssoInfo('Home Furnishing', 'Land Assets & Infrastructure', 250000, 30000, 1460, 50, 500, 5750, 2500, 2500, False, False, 20, False, False, None),
    33: FssoInfo('My Prop Funded Dream', 'High-Level FX Trading', 5000000, None, None, None, None, None, None, None, True, True, 30, False, False, None),
    34: FssoInfo('My FX Trader Bot', 'High-Level FX Trading', 5500000, None, None, None, None, None, None, None, True, True, 30, False, False, None),
    35: FssoInfo('Last Destination', 'High-Level FX Trading', 2000000, None, None, 50, 4500, 57000, 25000, 25000, True, False, 20, False, False, None),
}

def is_lifetime(fsso_no: int) -> bool:
    return FSSO_SCHEDULE[fsso_no].is_lifetime

def today_lagos() -> date:
    return datetime.now(LAGOS).date()

def is_business_day(d: date, holidays: frozenset[date] = frozenset()) -> bool:
    return d.weekday() < 5 and d not in holidays

def first_business_day_on_or_after(d: date, holidays: frozenset[date] = frozenset()) -> date:
    while not is_business_day(d, holidays):
        d += timedelta(days=1)
    return d

def last_day_of_month(d: date) -> date:
    year = d.year + (d.month // 12)
    month = d.month % 12 + 1
    return date(year, month, 1) - timedelta(days=1)

def is_funding_window(d: date) -> bool:
    return d >= last_day_of_month(d) - timedelta(days=6)

def first_cycle_start(funding_date: date, holidays: frozenset[date] = frozenset()) -> date:
    if not is_funding_window(funding_date):
        raise ValueError("New FSSOs can only be funded in the last 7 days of a month.")
    year = funding_date.year + (funding_date.month // 12)
    month = funding_date.month % 12 + 1
    return first_business_day_on_or_after(date(year, month, 1), holidays)

def next_cycle_start(after: date, holidays: frozenset[date] = frozenset()) -> date:
    monday_next_week = after + timedelta(days=7 - after.weekday())
    return first_business_day_on_or_after(monday_next_week, holidays)

def renewal_available_from(duration_end: date) -> date:
    return duration_end + timedelta(days=RENEWAL_REST_DAYS)

def free_fsso1_deletion_date(registered_on: date) -> date:
    return registered_on + timedelta(days=FREE_FSSO1_DELETION_DAYS)

def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def subsequent_capital_cap(total_gifted_profit, deployed_elsewhere=0) -> Decimal:
    remaining = Decimal(str(total_gifted_profit)) - Decimal(str(deployed_elsewhere))
    return _money(max(remaining, Decimal("0")) * SUBSEQUENT_CAPITAL_RATIO)

def check_funding_amount(amount, fsso_min_balance, lifetime_profit_share_total, deployed_elsewhere=0) -> tuple[bool, str]:
    amount, minimum = _money(amount), _money(fsso_min_balance)
    cap = subsequent_capital_cap(lifetime_profit_share_total, deployed_elsewhere)
    if minimum > cap:
        return False, f"This FSSO needs at least {minimum}, above your current limit of {cap}."
    if amount < minimum:
        return False, f"The designated minimum for this FSSO is {minimum}."
    if amount > cap:
        return False, f"You may use up to {cap} (50% of your lifetime profit shares)."
    return True, "OK"

def loss_recovery_cap(lifetime_profit_share_total) -> Decimal:
    return subsequent_capital_cap(lifetime_profit_share_total)

def cycle_allowed(fsso_no: int, cycle_no: int) -> bool:
    return fsso_no == 1 or cycle_no <= MAX_TRADE_CYCLES

def lifetime_summary(won_amounts: list) -> dict:
    total = sum((Decimal(str(a)) for a in won_amounts), Decimal("0"))
    return {
        "won_count": len(won_amounts),
        "lifetime_gift": _money(total),
        "investment_ceiling": subsequent_capital_cap(total),
    }

def new_fsso_report_text(summary: dict) -> str:
    return (
        "📊 Your lifetime summary\n"
        f"Trades won so far: {summary['won_count']}\n"
        f"Lifetime cumulative cash gift received: ${summary['lifetime_gift']}\n\n"
        "Reminder: you cannot invest more than 50% of that sum "
        f"(${summary['investment_ceiling']}) in your new FSSO."
    )

def fees_in_usd(fsso_no: int, ngn_per_usd, include_renewal: bool = False) -> Decimal:
    info = FSSO_SCHEDULE[fsso_no]
    naira = info.admin_fee_ngn + (info.renewal_fee_ngn or 0 if include_renewal else 0)
    return _money(Decimal(naira) / Decimal(str(ngn_per_usd)))

def net_balance_usd(fsso_no: int, ngn_per_usd, include_renewal: bool = False) -> Decimal | None:
    info = FSSO_SCHEDULE[fsso_no]
    remainder = info.fet_remainder_usd
    if remainder is None or info.slave_min_usd is None:
        return None
    return _money(Decimal(remainder) - Decimal(info.slave_min_usd) - fees_in_usd(fsso_no, ngn_per_usd, include_renewal))

def requires_exit_acknowledgement(fsso_no: int) -> bool:
    return FSSO_SCHEDULE[fsso_no].exits_rds

def eligible_fssos(lifetime_profit_share_total, deployed_elsewhere=0) -> list[int]:
    cap = subsequent_capital_cap(lifetime_profit_share_total, deployed_elsewhere)
    return [n for n, info in sorted(FSSO_SCHEDULE.items())
            if n != 1 and info.slave_min_usd is not None and _money(info.slave_min_usd) <= cap]

def check_funding_for_fsso(fsso_no: int, amount, lifetime_profit_share_total, deployed_elsewhere=0) -> tuple[bool, str]:
    minimum = FSSO_SCHEDULE[fsso_no].slave_min_usd
    if minimum is None:
        return False, "No funding minimum is set for this FSSO."
    return check_funding_amount(amount, minimum, lifetime_profit_share_total, deployed_elsewhere)

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
            return False, "FSSO1 and FSSO2 must run one after the other, never together."
        return True, "OK"

    if fsso_no == 2:
        if 1 not in completed:
            return False, "Complete FSSO1 before FSSO2."
        if active:
            return False, "FSSO1 and FSSO2 must run one after the other, never together."
        return True, "OK"

    if 2 not in completed:
        return False, "Complete foundational FSSO2 before unlocking other pipelines."
        
    if fsso_no == 25:
        if user_gender.lower() != "female":
            return False, "FSSO25 allocation is strictly limited to female members."
        if user_age < 23:
            return False, "FSSO25 requires a minimum profile metric of 23 years of age."
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

def disqualification_notice(reason: str, rule_key: str | None = None) -> str:
    return f"{reason}\n\n{WAIVER_SUFFIX if rule_key in WAIVER_AVAILABLE else NO_WAIVER_SUFFIX}"

def age_requirement_met(fsso_no: int, age: int, waiver_granted: bool = False) -> tuple[bool, str]:
    info = FSSO_SCHEDULE[fsso_no]
    if age < MIN_AGE:
        return False, disqualification_notice(f"You must be at least {MIN_AGE} years old.")
    if age >= info.age_limit:
        return True, "OK"
    if info.age_waivable and waiver_granted:
        return True, "OK (age requirement waived)"
    key = "age_requirement_intensive_medicare" if info.age_waivable else None
    return False, disqualification_notice(f"This FSSO needs a minimum age of {info.age_limit}.", key)

NONE_OPTION = "NONE"                 
REFERRING_EXECS = ["GMD"] + [f"ED{i}" for i in range(1, 12)] + [f"CEO{i}" for i in range(1, 51)]

def round_robin_next(last_assigned: dict) -> str:
    def key(item):
        i, name = item
        when = last_assigned.get(name)
        return (when is not None, when or datetime.min.replace(tzinfo=LAGOS), i)
    return min(enumerate(REFERRING_EXECS), key=key)

GUARANTOR_MIN_AGE = 25               
GUARANTOR_CATEGORIES = ("rds_member", "spouse", "parent", "uncle_cousin_or_nephew")

def guarantor_eligible(category: str, age: int, telegram_age_months: float) -> tuple[bool, str]:
    if category not in GUARANTOR_CATEGORIES:
        return False, "Guarantor classification out of compliance profiles."
    if age < GUARANTOR_MIN_AGE:
        return False, f"Guarantor profile metrics do not satisfy the minimum requirement of {GUARANTOR_MIN_AGE}."
    if telegram_age_months < 6.0:
        return False, "Target Telegram account must possess a verified footprint age of at least 6 months."
    return True, "OK"

def checkin_week(moment: datetime) -> tuple[datetime, datetime]:
    m = moment.astimezone(LAGOS)
    days_since_sunday = (m.weekday() + 1) % 7
    start = (m - timedelta(days=days_since_sunday)).replace(hour=0, minute=1, second=0, microsecond=0)
    end = (start + timedelta(days=6)).replace(hour=23, minute=59, second=0, microsecond=0)
    return start, end
