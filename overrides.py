"""
The GMD override register.

The GMD may override a critical requirement for a user, an ED or a CEO, but not every rule is safe
to override: some rules hold other rules up (money, fairness, legal promises). Each rule below is
classified, and the classification is enforced by code, so an override can never quietly break
the interdependencies of the RDS.

  SAFE         the GMD may override with a recorded reason; nothing else has to change.
  CONDITIONAL  the GMD may override only if the listed follow-on changes happen automatically
               (the "cascade"); high-impact ones also need a named second approver.
  LOCKED       cannot be overridden in the app by anyone. Changing it means changing the
               blueprint and the code, and (for legal items) getting counsel's agreement.

This register is versioned and kept up to date as the RDS grows (see REGISTER_VERSION).
"""
import os
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger("repellano.overrides")

REGISTER_VERSION = "1.3 (30 Oct 2026)"
SAFE, CONDITIONAL, LOCKED = "SAFE", "CONDITIONAL", "LOCKED"
MIN_REASON_CHARS = 15
GMD_IDS = {int(x) for x in os.getenv("GMD_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}
# Second approvers are Executive Directors named by the GMD (Telegram IDs, comma separated, set on Render
# as ED_APPROVER_IDS). Until at least one is named, overrides that need a second approver cannot be granted.
APPROVER_IDS = {int(x) for x in os.getenv("ED_APPROVER_IDS", "").replace(" ", "").split(",") if x.lstrip("-").isdigit()}


@dataclass(frozen=True)
class Rule:
    key: str
    title: str
    applies_to: str            # user | ED | CEO | system
    cls: str                   # SAFE | CONDITIONAL | LOCKED
    may_do: str                # what the GMD may do (or why it is locked)
    cascade: str               # what must happen automatically (or what it protects)
    depends_on: str            # the rules it is tied to
    second_approval: bool = False   # recommended: a named second approver
    needs_expiry: bool = False      # the override must be time-boxed
    line_override: bool = False     # the member's own CEO (first approval) and ED (final approval) may also grant it


REGISTER: list[Rule] = [
    # ---------------- members ----------------
    Rule("lead_free_window", "30-day free FSSO1 window", "user", SAFE,
         "Extend a lead's 30 days before the profile is deleted.",
         "The deletion date moves; nothing else.", "Account deletion", needs_expiry=True),
    Rule("dormant_reactivation", "Dormant member reactivation", "user", SAFE,
         "Reactivate a dormant member's journey.",
         "Status returns to active; deposit stays in escrow.", "Dormant customers"),
    Rule("fine_waive", "Fine waiver or reduction", "user", CONDITIONAL,
         "Waive or reduce a Resident's or Citizen's fine, or lift the freeze.",
         "Fine record updated, freeze lifted only after the waiver is logged or Korapay confirms payment; access restored with the usual notice.",
         "Fine enforcement, Korapay confirmation"),
    Rule("tier_grant", "Grant or restore a tier", "user", CONDITIONAL,
         "Grant or restore VIP, Resident or Citizen (including a free upgrade).",
         "FSSO and guarantee limits, fine range and privileges switch to the new tier together; the waived application fee is recorded as complimentary.",
         "Tier limits, fines, guarantees, application fees", second_approval=True),
    Rule("banish_reversal", "Lift a banishment", "user", CONDITIONAL,
         "Reinstate a banished Paid member.",
         "Guarantor is notified; reputational-collateral records are updated; the original infraction stays on file.",
         "Conduct standards, guarantees", second_approval=True),
    Rule("extra_slot", "Extra simultaneous FSSO", "user", CONDITIONAL,
         "Allow one more FSSO activated at once.",
         "A separate linked account is required for the extra FSSO; the slot is counted against the member and the override expires.",
         "Tier limits, one linked account per FSSO", needs_expiry=True),
    Rule("extra_guarantees", "Extra guarantees", "user", CONDITIONAL,
         "Raise a member's guarantee limit.",
         "The guarantee count and every guarantor's exposure are recomputed; the override expires.",
         "Guarantee limits", needs_expiry=True),
    Rule("funding_window_exception", "Funding outside the last 7 days", "user", CONDITIONAL,
         "Allow one funding date outside the window.",
         "Activation stays on the first working day of the following month after the funding date; the Master sweep schedule is unchanged.",
         "Funding window, first working day, daily sweep", needs_expiry=True),
    Rule("renewal_pause_shorten", "Shorten the 2-week renewal pause", "user", CONDITIONAL,
         "End the compulsory pause early for a renewable FSSO.",
         "Only after the locked duration has ended; the Renewal Fee is still built into the renewed target. Never for lifetime FSSOs.",
         "Locked duration, renewal, lifetime rule"),
    Rule("admin_fee_waive", "Waive or reduce an Admin or Renewal Fee", "user", CONDITIONAL,
         "Waive or reduce a fee.",
         "The Final Equity Target and the payout split are recalculated automatically; the member is repaid first as usual.",
         "Fees built into the FET, payout order", second_approval=True),
    Rule("cycle_cap_extra", "More than 3 trade cycles", "user", CONDITIONAL,
         "Offer a further trade cycle.",
         "RNL's maximum exposure for that member is set and recorded; the new cycle keeps the recovery target and profit-share limits.",
         "Cycle cap, RNL bears trading losses", second_approval=True, needs_expiry=True),
    Rule("capital_ceiling_raise", "Raise the 50% capital ceiling", "user", CONDITIONAL,
         "Allow a larger starting balance than 50% of lifetime profit shares.",
         "RNL's exposure is capped and recorded; the FSSO minimum balance still applies.",
         "50% ceiling, gifted loan, RNL bears trading losses", second_approval=True, needs_expiry=True),
    Rule("sequence_skip", "Skip or unlock FSSO1 or FSSO2 early", "user", CONDITIONAL,
         "Let a member past the FSSO1 to FSSO2 gate.",
         "A starting balance funded by RNL must be named, because no gifted loan exists yet; lifetime win counters are not edited; the skipped FSSO is recorded as waived.",
         "FSSO gating, starter loan, capital ceiling", second_approval=True),
    Rule("fsso1_funding_timeout", "FSSO1 one-hour funding rule", "user", CONDITIONAL,
         "Waive the restriction for good reason (glitch, network downtime or another reasonable explanation from the customer).",
         "The 6-month restriction is lifted and the $10 deposit is not forfeited; the $10 loan is recorded as repaid or waived so RNL's records balance; the member is notified and may start again immediately.",
         "FSSO1 loan loop, deposit escrow, absconding protection", second_approval=True, line_override=True),
    Rule("remittance_timeout", "One-hour profit-share remittance rule", "user", CONDITIONAL,
         "Waive the lifetime ban for a late remittance for good reason (glitch, network downtime or another reasonable explanation).",
         "The ban is held; the member gets one more hour to pay the outstanding amount, failing which the ban becomes permanent; the waiver and both approvals are recorded; the member is notified.",
         "Profit-share remittance, bans, member's line (CEO then ED)", second_approval=True, line_override=True),
    Rule("deposit_early_refund", "Refund the $10 deposit early", "user", CONDITIONAL,
         "Ask the escrow provider to release a deposit early.",
         "Only through the escrow provider, never by RNL; not available while a $10 trading fund is outstanding.",
         "Deposit escrow, absconding protection"),
    # ---------------- leadership ----------------
    Rule("swap_ed", "Swap an Executive Director", "ED", CONDITIONAL,
         "Replace an ED.",
         "Domino effect: CEO reporting lines move, commissions are recalculated, lists update, history is re-based.",
         "Leadership structure, commissions", second_approval=True),
    Rule("reassign_ceo", "Reassign or replace a CEO", "CEO", CONDITIONAL,
         "Move a CEO to another ED or replace them.",
         "Reporting line and commission routing update together; history is re-based.",
         "Leadership structure, commissions"),
    Rule("commission_adjust", "Adjust a commission", "ED", CONDITIONAL,
         "Change an ED's or CEO's commission.",
         "Every day since the change date is recalculated and the to-date total corrected.",
         "Commissions, smart memory", second_approval=True),
    Rule("leadership_suspend", "Suspend an ED or CEO", "ED", SAFE,
         "Suspend or reinstate an ED or CEO.",
         "Status changes; reporting lines stay unless a swap is made.", "Leadership structure"),
    # ---------------- locked ----------------
    Rule("min_age", "Minimum age of 20", "user", LOCKED,
         "Cannot be waived.", "Legal protection for members and RNL.", "Admission"),
    Rule("conduct_standards", "Conduct standards (no drugs, drunkenness, violence, prostitution)", "user", LOCKED,
         "Cannot be waived for admission. A banned member can only return through a recorded banishment reversal.",
         "Protects every member and every guarantor.", "Admission, guarantees"),
    Rule("deposit_escrow", "The $10 deposit stays with the third-party escrow", "system", LOCKED,
         "RNL never collects or touches it.", "Core promise to members and the basis of the guarantor-free starter loan.", "Starter loan, wording promises"),
    Rule("member_funds_never_traded", "Linked accounts are funded from the gifted loan only", "system", LOCKED,
         "Cannot be changed for one member.", "Keeps the 'never trade with your money' promise true.", "Capital rules, wording promises"),
    Rule("payout_order", "Member is repaid first at settlement", "system", LOCKED,
         "Cannot be reordered.", "Contract promise on loss-recovery cycles.", "Loss recovery, FET"),
    Rule("no_repayment_demand", "Gifted loan is never asked back", "system", LOCKED,
         "Cannot be changed for one member.", "Contract promise to members.", "Gifted loan"),
    Rule("one_slave_per_active_fsso", "Dedicated Master account per FSSO; one linked account per activated FSSO", "system", LOCKED,
         "Cannot be bypassed.", "Trade copying and balance sweeps depend on it.", "Master/Slave structure, daily sweep"),
    Rule("no_duplicate_fsso", "No two of the same FSSO at once", "system", LOCKED,
         "Cannot be bypassed.", "Prevents double-counting of targets and payouts.", "Duplicate cycles, FET"),
    Rule("locked_duration_never_extends", "The locked duration never extends once started", "system", LOCKED,
         "Cannot be extended.", "Its purpose is to prevent abuse and promote responsibility.", "Duration, renewal"),
    Rule("lifetime_once", "Lifetime FSSOs are activated only once", "system", LOCKED,
         "No second activation.", "Part of the product definition and the FET maths.", "Lifetime FSSOs, renewal"),
    Rule("trading_balance_gate", "Trading starts only when the Master balance is equal to or lower than the linked account's balance", "system", LOCKED,
         "Cannot be bypassed.", "Protects the trade-copying structure between Master and linked accounts.", "Master/Slave structure, daily sweep, funded minimums"),
    Rule("override_audit", "The audit trail and this register", "system", LOCKED,
         "Cannot be switched off, edited or deleted.", "Every other safeguard relies on it.", "All overrides"),
]

_BY_KEY = {r.key: r for r in REGISTER}


def get_rule(key: str) -> Rule | None:
    return _BY_KEY.get(key)


def is_gmd(telegram_id: int) -> bool:
    return telegram_id in GMD_IDS


def check_request(rule_key: str, reason: str, granted_by: int, approved_by: int | None = None,
                  expires_at: datetime | None = None, target_id: int | None = None) -> tuple[bool, str]:
    """Decide whether an override may be recorded. Pure function, easy to test."""
    rule = get_rule(rule_key)
    if rule is None:
        return False, "Unknown rule: it is not in the override register."
    if not is_gmd(granted_by):
        return False, "Only the GMD can grant an override."
    if rule.cls == LOCKED:
        return False, f"'{rule.title}' is locked and cannot be overridden."
    if len((reason or "").strip()) < MIN_REASON_CHARS:
        return False, f"A reason of at least {MIN_REASON_CHARS} characters is required."
    if rule.second_approval:
        if not APPROVER_IDS:
            return False, "This override needs a second approver, and no Executive Director has been named yet."
        if approved_by is None or approved_by not in APPROVER_IDS:
            return False, "This override needs a second approver who is a named Executive Director."
        if approved_by == granted_by or (target_id is not None and approved_by == target_id):
            return False, "The second approver cannot be the GMD or the person the override is about."
    if rule.needs_expiry:
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            return False, "This override must have a future expiry date."
    return True, "OK"


LINE_REASONS = ("glitch", "network_downtime", "other_reasonable")


def check_line_override(rule_key: str, reason_category: str, reason: str, first_approver: int,
                        final_approver: int, member_ceo_id: int | None, member_ed_id: int | None,
                        member_id: int | None = None) -> tuple[bool, str]:
    """The member's own line may waive certain rules: the linked CEO gives first approval and the
    linked ED gives the final approval. Pure function, easy to test."""
    rule = get_rule(rule_key)
    if rule is None or not rule.line_override:
        return False, "This rule cannot be overridden by the member's line."
    if reason_category not in LINE_REASONS:
        return False, "Choose a reason: glitch, network downtime, or another reasonable explanation."
    if len((reason or "").strip()) < MIN_REASON_CHARS:
        return False, f"A reason of at least {MIN_REASON_CHARS} characters is required."
    if member_ceo_id is None or member_ed_id is None:
        return False, "The member has no linked CEO and ED on record."
    if first_approver != member_ceo_id:
        return False, "First approval must come from the member's linked CEO."
    if final_approver != member_ed_id:
        return False, "Final approval must come from the member's linked ED."
    if member_id is not None and member_id in (first_approver, final_approver):
        return False, "Nobody can approve an override about themselves."
    return True, "OK"


async def grant_line_override(rule_key: str, member_id: int, reason_category: str, reason: str,
                              first_approver: int, final_approver: int,
                              member_ceo_id: int | None, member_ed_id: int | None) -> tuple[bool, str, int | None]:
    """Record a line override. The CEO's first approval and the ED's final approval are both saved."""
    import db
    ok, message = check_line_override(rule_key, reason_category, reason, first_approver, final_approver,
                                      member_ceo_id, member_ed_id, member_id)
    if not ok:
        return False, message, None
    new_id = await db.record_override(rule_key, "user", member_id, reason_category, reason.strip(),
                                      first_approver, final_approver, None)
    log.info("Line override %s on member %s: CEO %s then ED %s", rule_key, member_id, first_approver, final_approver)
    return True, "Override recorded. The member may start again immediately.", new_id


async def grant(rule_key: str, target_type: str, target_id: int, reason: str, granted_by: int,
                value: str | None = None, approved_by: int | None = None,
                expires_at: datetime | None = None) -> tuple[bool, str, int | None]:
    """Validate and record an override (the record is the audit trail)."""
    import db
    ok, message = check_request(rule_key, reason, granted_by, approved_by, expires_at, target_id)
    if not ok:
        return False, message, None
    if target_type not in ("user", "ed", "ceo"):
        return False, "Target must be user, ed or ceo.", None
    new_id = await db.record_override(rule_key, target_type, target_id, value, reason.strip(),
                                      granted_by, approved_by, expires_at)
    log.info("Override %s granted on %s %s by %s", rule_key, target_type, target_id, granted_by)
    return True, "Override recorded.", new_id


def register_rows() -> list[tuple]:
    """Rows for the blueprint table: class, title, applies to, what may be done, cascade, depends on."""
    order = {SAFE: 0, CONDITIONAL: 1, LOCKED: 2}
    return [(r.cls, r.title, r.applies_to, r.may_do, r.cascade, r.depends_on, r.second_approval, r.needs_expiry)
            for r in sorted(REGISTER, key=lambda r: order[r.cls])]
