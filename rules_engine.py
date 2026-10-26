"""
RDS General Rules & Limitations: backend rules engine.

Pure functions only (no Telegram, no database), so every rule can be tested in
isolation and called from any handler before a member reaches the next phase.

Rules that are still open in the blueprint (penalties for Paid/VIP members,
renewal-fee payment, business-day holidays) are deliberately NOT implemented.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

LAGOS = ZoneInfo("Africa/Lagos")

# --- CONSTANTS FROM THE RULES ---
MIN_AGE = 20
TOTAL_FSSOS = 35
COMPULSORY = (1, 2)                       # taken in order, never together, once each
SUBSEQUENT_CAPITAL_RATIO = Decimal("0.5")  # 50% of accumulated WON profit shares
RENEWAL_REST_DAYS = 14
FREE_FSSO1_DELETION_DAYS = 30


@dataclass(frozen=True)
class Tier:
    name: str
    max_simultaneous: int          # FSSOs ACTIVATED at the same time
    max_guarantees: int
    can_be_banished: bool
    fine_range_ngn: tuple[int, int] | None  # None = no fine defined / not applicable
    application_fee_ngn: int = 0
    can_sell_guarantees: bool = False


GUARANTEE_SALE_PRICE_NGN = 50_000
MAX_DISTINCT_UNLESS_UPGRADED = 3   # more than 3 different FSSOs needs VIP, Resident or Citizen
MAX_TRADE_CYCLES = 3               # [OPEN] what happens after 3 LOSSes; is the FSSO1 loan loop also capped?

TIERS: dict[str, Tier] = {
    "lead": Tier("Registered Lead", 1, 0, False, None),                       # FSSO1 only, 30 days free
    "paid": Tier("Paid Client / Lead", 3, 4, True, None),                     # no fine stated
    "vip": Tier("VIP", 4, 6, False, None, 250_000),                           # serious breach: back to Paid, no refund
    "resident": Tier("Repellano Resident", 5, 8, False, (2_000_000, 3_000_000), 1_000_000, True),
    "citizen": Tier("Repellano Citizen", 6, 10, False, (3_500_000, 5_000_000), 3_000_000, True),
}


# --- FEES, DEPOSIT AND SCHEDULE (from FSSO_Matrix.xlsx) ---
STARTER_LOAN_USD = 10          # FSSO1 only; given again after every LOSS until a WIN
SECURITY_DEPOSIT_USD = 10      # FSSO1 only; paid once, held in escrow, returned on the first WIN


@dataclass(frozen=True)
class FssoInfo:
    name: str
    admin_fee_ngn: int               # built into the FET, paid at settlement
    renewal_fee_ngn: int | None      # None = not renewable
    duration_days: int | None        # None = lifetime (activated only once)

    @property
    def is_lifetime(self) -> bool:
        return self.duration_days is None


FSSO_SCHEDULE: dict[int, FssoInfo] = {
    1: FssoInfo('Starter Trader Fund', 20000, None, None),
    2: FssoInfo('Rainy Day Fund', 20000, None, None),
    3: FssoInfo('My Daily Meal', 20000, 30000, 90),
    4: FssoInfo('My Annual Rent', 20000, 30000, 365),
    5: FssoInfo('My Annual Clothing', 20000, 30000, 365),
    6: FssoInfo('My Health Insurance', 20000, 30000, 365),
    7: FssoInfo('My New Phone', 20000, 30000, 1460),
    8: FssoInfo('My Monthly Bills', 20000, 30000, 365),
    9: FssoInfo('My Weekend Pepper soup', 20000, 30000, 90),
    10: FssoInfo('My Vacation Fund', 20000, 30000, 365),
    11: FssoInfo('My Cancer Medics Fund', 20000, 30000, 90),
    12: FssoInfo('My Dialysis Fund', 20000, 30000, 60),
    13: FssoInfo('My Surgery Fund', 20000, 30000, 365),
    14: FssoInfo('My IVF Fund', 20000, 30000, 730),
    15: FssoInfo('My Point-of-Sale Biz', 20000, 30000, 365),
    16: FssoInfo('My Mini Importation Biz', 20000, 30000, 365),
    17: FssoInfo('I Work with My Hands', 20000, 30000, 365),
    18: FssoInfo('My Starter Farm Biz', 20000, 30000, 365),
    19: FssoInfo('My Ice Block Biz', 20000, 30000, 365),
    20: FssoInfo('My Party Rentals Biz', 20000, 30000, 365),
    21: FssoInfo('Buy & Sell Biz (Market Trader)', 20000, 30000, 365),
    22: FssoInfo('My Tractor Rider Biz', 20000, 30000, 365),
    23: FssoInfo('My School Fees', 20000, 30000, 365),
    24: FssoInfo('Our Wedding Expenses', 20000, None, None),
    25: FssoInfo('Our New Baby Fund', 20000, 30000, 730),
    26: FssoInfo('My Pension Booster', 20000, None, None),
    27: FssoInfo('My Japa Dream', 20000, 30000, 365),
    28: FssoInfo('My Plot of Land', 100000, None, None),
    29: FssoInfo('Secure My Land', 100000, None, None),
    30: FssoInfo('Build My Shelter', 100000, None, None),
    31: FssoInfo('My Solar Power Fund', 100000, 30000, 1460),
    32: FssoInfo('Home Furnishing', 100000, 30000, 1460),
    33: FssoInfo('My Prop Funded Dream', 75000, None, None),
    34: FssoInfo('My FX Trader Bot', 50000, None, None),
    35: FssoInfo('Level by Level', 100000, None, None),
}


def is_lifetime(fsso_no: int) -> bool:
    return FSSO_SCHEDULE[fsso_no].is_lifetime


# --- CALENDAR RULES (all dates are Lagos calendar dates) ---
def today_lagos() -> date:
    return datetime.now(LAGOS).date()


def is_business_day(d: date, holidays: frozenset[date] = frozenset()) -> bool:
    """Monday to Friday, excluding any supplied public holidays [OPEN: confirm]."""
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
    """A NEW FSSO may only be funded during the last 7 days of a month.
    [OPEN: does the weekend-only restriction still apply inside that window?]"""
    return d >= last_day_of_month(d) - timedelta(days=6)


def first_cycle_start(funding_date: date, holidays: frozenset[date] = frozenset()) -> date:
    """First cycle of a new FSSO (activation): first working day of the month
    AFTER the funding month. Applies to all FSSOs."""
    if not is_funding_window(funding_date):
        raise ValueError("New FSSOs can only be funded in the last 7 days of a month.")
    year = funding_date.year + (funding_date.month // 12)
    month = funding_date.month % 12 + 1
    return first_business_day_on_or_after(date(year, month, 1), holidays)


def next_cycle_start(after: date, holidays: frozenset[date] = frozenset()) -> date:
    """For an already activated FSSO (e.g. after a LOSS): funding for the new cycle
    opens immediately; trading begins on the first trading day of NEXT week,
    even if that week falls in a new month."""
    monday_next_week = after + timedelta(days=7 - after.weekday())
    return first_business_day_on_or_after(monday_next_week, holidays)


def renewal_available_from(duration_end: date) -> date:
    """The locked duration starts only after the Final Equity Target is reached and
    every payout is made, and never extends. Renewal is possible only after the
    duration ends plus the 2-week (14-day) compulsory pause.
    Lifetime-duration FSSOs can be activated only once (no renewal)."""
    return duration_end + timedelta(days=RENEWAL_REST_DAYS)


def free_fsso1_deletion_date(registered_on: date) -> date:
    """Unpaid free FSSO1 accounts are deleted 30 days after registration."""
    return registered_on + timedelta(days=FREE_FSSO1_DELETION_DAYS)


# --- MONEY RULES ---
def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def subsequent_capital_cap(total_gifted_profit) -> Decimal:
    """After FSSO1: capital for a new FSSO <= 50% of the member's lifetime profit-share total."""
    return _money(Decimal(str(total_gifted_profit)) * SUBSEQUENT_CAPITAL_RATIO)


def check_funding_amount(amount, fsso_min_balance, lifetime_profit_share_total) -> tuple[bool, str]:
    """
    Funding for a NEW FSSO after FSSO1. The linked account is funded from the gifted loan.
      - Ceiling: up to 50% of the member's LIFETIME profit-share total.
      - The RDS always insists on the FSSO's designated minimum balance.
    Every FSSO activated at the same time has its own 50% ceiling.
    """
    amount, minimum = _money(amount), _money(fsso_min_balance)
    cap = subsequent_capital_cap(lifetime_profit_share_total)
    if minimum > cap:
        return False, f"This FSSO needs at least {minimum}, above your current limit of {cap}."
    if amount < minimum:
        return False, f"The designated minimum for this FSSO is {minimum}."
    if amount > cap:
        return False, f"You may use up to {cap} (50% of your lifetime profit shares)."
    return True, "OK"


def loss_recovery_cap(lifetime_profit_share_total) -> Decimal:
    """Trade cycle 2 after a LOSS may use up to ANOTHER 50% of the lifetime total
    (e.g. a further $200 on $400). The RDS still asks only for the stipulated minimum."""
    return subsequent_capital_cap(lifetime_profit_share_total)


def cycle_allowed(fsso_no: int, cycle_no: int) -> bool:
    """The RDS offers at most 3 trade cycles (FSSO1's loan loop repeats until a WIN)."""
    return fsso_no == 1 or cycle_no <= MAX_TRADE_CYCLES


def lifetime_summary(won_amounts: list) -> dict:
    """Count of ALL trades WON across every FSSO, the lifetime cumulative cash gift
    received (sum of WON profit shares), and the 50% investment ceiling."""
    total = sum((Decimal(str(a)) for a in won_amounts), Decimal("0"))
    return {
        "won_count": len(won_amounts),
        "lifetime_gift": _money(total),
        "investment_ceiling": subsequent_capital_cap(total),
    }


def new_fsso_report_text(summary: dict) -> str:
    """Brief report shown when a client launches a new FSSO."""
    return (
        "📊 Your lifetime summary\n"
        f"Trades won so far: {summary['won_count']}\n"
        f"Lifetime cumulative cash gift received: ${summary['lifetime_gift']}\n\n"
        "Reminder: you cannot invest more than 50% of that sum "
        f"(${summary['investment_ceiling']}) in your new FSSO."
    )


def net_gift_report(won_amounts: list, loss_amounts: list) -> dict:
    """Count and sum of WON and LOSS cycles plus the NET cumulative figure,
    pushed to the member whenever they launch a new FSSO."""
    won = sum((Decimal(str(a)) for a in won_amounts), Decimal("0"))
    loss = sum((Decimal(str(a)) for a in loss_amounts), Decimal("0"))
    return {
        "won_count": len(won_amounts), "won_total": _money(won),
        "loss_count": len(loss_amounts), "loss_total": _money(loss),
        "net": _money(won - loss),
    }


def fine_in_range(tier_key: str, amount_ngn: int) -> bool:
    rng = TIERS[tier_key].fine_range_ngn
    return bool(rng) and rng[0] <= amount_ngn <= rng[1]


# --- ACCESS GATEKEEPING ---
def check_fsso_access(fsso_no: int, tier_key: str, completed: set[int], active: set[int]) -> tuple[bool, str]:
    """
    Decide whether a member may start FSSO `fsso_no` right now.
      completed: FSSOs the member has finished
      active:    FSSOs currently ACTIVATED (trading commenced and not yet settled);
                 an FSSO in its locked duration does NOT count
    Returns (allowed, reason).
    """
    if not 1 <= fsso_no <= TOTAL_FSSOS:
        return False, "That FSSO does not exist."
    if tier_key == "lead" and fsso_no != 1:
        return False, "Registered leads can only use FSSO1. Upgrade to Paid first."
    if fsso_no in active:
        return False, "This FSSO is already activated; duplicate cycles are not allowed."
    if fsso_no in COMPULSORY and fsso_no in completed:
        return False, "Compulsory FSSOs can only be taken once in a lifetime."

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

    # FSSO3 to FSSO35
    if 2 not in completed:
        return False, "Complete FSSO2 before unlocking the other FSSOs."
    tier = TIERS[tier_key]
    if len(active) >= tier.max_simultaneous:
        return False, f"Your tier ({tier.name}) allows {tier.max_simultaneous} FSSOs activated at a time."
    return True, "OK"


if __name__ == "__main__":
    # Quick self-check
    assert is_funding_window(date(2026, 10, 25))                     # last 7 days of Oct
    assert not is_funding_window(date(2026, 10, 24))                 # 8th day from the end
    assert not is_funding_window(date(2026, 10, 3))                  # first weekend: not allowed
    assert first_cycle_start(date(2026, 10, 28)) == date(2026, 11, 2)  # Mon 2 Nov
    assert first_cycle_start(date(2026, 12, 28)) == date(2027, 1, 1)   # year roll-over, Fri
    assert next_cycle_start(date(2026, 10, 30)) == date(2026, 11, 2)   # Fri -> next Mon
    assert renewal_available_from(date(2026, 12, 1)) == date(2026, 12, 15)
    assert subsequent_capital_cap(1000) == Decimal("500.00")
    assert len(FSSO_SCHEDULE) == 35
    assert [n for n in FSSO_SCHEDULE if is_lifetime(n)] == [1, 2, 24, 26, 28, 29, 30, 33, 34, 35]
    assert FSSO_SCHEDULE[7].duration_days == 1460 and FSSO_SCHEDULE[7].renewal_fee_ngn == 30000
    assert FSSO_SCHEDULE[28].admin_fee_ngn == 100000
    assert loss_recovery_cap(400) == Decimal("200.00")
    assert check_funding_amount(150, 150, 400)[0] is True      # minimum within the $200 cap
    assert check_funding_amount(250, 150, 400)[0] is False     # above 50% of 400
    assert check_funding_amount(100, 150, 400)[0] is False     # below the designated minimum
    assert check_funding_amount(150, 250, 400)[0] is False     # minimum itself above the cap
    assert check_fsso_access(2, "paid", set(), set())[0] is False
    assert check_fsso_access(3, "paid", {1, 2}, {5, 6, 7})[0] is False
    assert check_fsso_access(3, "vip", {1, 2}, {5, 6})[0] is True
    assert check_fsso_access(3, "vip", {1, 2}, {5, 6, 7, 8})[0] is False
    assert check_fsso_access(3, "lead", set(), set())[0] is False
    assert check_fsso_access(1, "lead", set(), set())[0] is True
    assert [(t.max_simultaneous, t.max_guarantees) for t in (TIERS["paid"], TIERS["vip"], TIERS["resident"], TIERS["citizen"])] == [(3, 4), (4, 6), (5, 8), (6, 10)]
    assert TIERS["resident"].can_sell_guarantees and not TIERS["paid"].can_sell_guarantees
    assert check_fsso_access(1, "paid", set(), set())[0] is True   # Paid keeps running FSSO1 until the first WIN
    assert check_fsso_access(1, "paid", {1}, set())[0] is False    # closed once completed
    assert cycle_allowed(5, 3) and not cycle_allowed(5, 4) and cycle_allowed(1, 9)
    assert lifetime_summary([100, 300])["investment_ceiling"] == Decimal("200.00")
    assert "50%" in new_fsso_report_text(lifetime_summary([100, 300]))
    print("rules_engine self-check passed")
