"""
RDS General Rules & Limitations: backend rules engine.

Pure functions only (no Telegram, no database), so every rule can be tested in
isolation and called from any handler before a member reaches the next phase.

Rules that the source files leave ambiguous are deliberately NOT implemented
(see "Open points" in the blueprint): duration semantics, loss-recovery capital,
penalties for Paid/VIP members.
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
    max_simultaneous: int
    max_guarantees: int
    can_be_banished: bool
    fine_range_ngn: tuple[int, int] | None  # None = no fine defined / not applicable


TIERS: dict[str, Tier] = {
    "paid": Tier("Paid Client / Lead", 2, 4, True, None),     # penalty not stated [OPEN]
    "vip": Tier("VIP", 3, 6, False, None),                    # serious breach: demoted to paid
    "resident": Tier("Repellano Resident", 4, 8, False, (2_000_000, 3_000_000)),
    "citizen": Tier("Repellano Citizen", 5, 10, False, (3_500_000, 5_000_000)),
}


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
    """After FSSO1: capital for a new FSSO <= 50% of accumulated WON profit shares.
    [OPEN: per new FSSO or lifetime total?]"""
    return _money(Decimal(str(total_gifted_profit)) * SUBSEQUENT_CAPITAL_RATIO)


def check_funding_amount(amount, fsso_min_balance, lifetime_profit_share_total) -> tuple[bool, str]:
    """
    Funding for a NEW FSSO after FSSO1. The linked account is funded from the gifted loan.
      - Ceiling: up to 50% of the member's LIFETIME profit-share total.
      - The RDS always insists on the FSSO's designated minimum balance.
    [OPEN: do FSSOs activated at once each get the 50% ceiling, or share one?]
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
    assert check_funding_amount(150, 150, 400)[0] is True      # minimum within the $200 cap
    assert check_funding_amount(250, 150, 400)[0] is False     # above 50% of 400
    assert check_funding_amount(100, 150, 400)[0] is False     # below the designated minimum
    assert check_funding_amount(150, 250, 400)[0] is False     # minimum itself above the cap
    assert check_fsso_access(2, "paid", set(), set())[0] is False
    assert check_fsso_access(3, "paid", {1, 2}, {5, 6})[0] is False
    assert check_fsso_access(3, "vip", {1, 2}, {5, 6})[0] is True
    print("rules_engine self-check passed")
