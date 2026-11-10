# -*- coding: utf-8 -*-
import os
import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

log = logging.getLogger("repellano.db")
TOTAL_SECTIONS = 6

try:
    import asyncpg
except Exception:
    asyncpg = None

def _clean_dsn(dsn: str) -> str:
    parts = urlsplit(dsn)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "channel_binding"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS members (
        telegram_id BIGINT PRIMARY KEY,
        first_name TEXT,
        anthem_lang TEXT,
        anthem_completed_at TIMESTAMPTZ,
        portal_completed SMALLINT NOT NULL DEFAULT 0,
        portal_completed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS events (
        id BIGSERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL,
        event TEXT NOT NULL,
        detail TEXT,
        at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS customer_fssos (
        id BIGSERIAL PRIMARY KEY,
        telegram_id BIGINT NOT NULL REFERENCES members(telegram_id) ON DELETE CASCADE,
        fsso_no SMALLINT NOT NULL,
        fsso_tag VARCHAR(10) NOT NULL,
        current_tier VARCHAR(20) NOT NULL DEFAULT 'lead',
        status VARCHAR(30) NOT NULL DEFAULT 'initialized',
        current_cycle SMALLINT NOT NULL DEFAULT 1,
        slave_account_id VARCHAR(50),
        master_account_id VARCHAR(50),
        initial_slave_balance NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
        proof_status VARCHAR(20) NOT NULL DEFAULT 'not_applicable',
        proof_document_url TEXT,
        funded_at TIMESTAMPTZ,
        activated_at TIMESTAMPTZ,
        settled_at TIMESTAMPTZ,
        duration_expires_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS fsso_cycles_history (
        id BIGSERIAL PRIMARY KEY,
        customer_fsso_id BIGINT NOT NULL REFERENCES customer_fssos(id) ON DELETE CASCADE,
        cycle_no SMALLINT NOT NULL,
        outcome VARCHAR(10) NOT NULL,
        ending_master_balance NUMERIC(12, 2) NOT NULL,
        ending_slave_balance NUMERIC(12, 2) NOT NULL,
        rnl_share_payout NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
        user_share_payout NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
        net_balance_payout NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
        settled_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )"""
]

class MemoryBackend:
    enabled = False
    def __init__(self):
        self.members = {}
    async def upsert_member(self, tid, first_name): self.members[tid] = {"first_name": first_name, "portal_completed": 0, "anthem_done": False}
    async def anthem_complete(self, tid, lang): 
        if tid in self.members: self.members[tid]["anthem_done"] = True
    async def member_state(self, tid):
        m = self.members.get(tid, {"anthem_done": False, "portal_completed": 0})
        return m["anthem_done"], m["portal_completed"]
    async def advance(self, tid, section):
        if tid in self.members and self.members[tid]["portal_completed"] == section:
            self.members[tid]["portal_completed"] += 1
        return self.members.get(tid, {"portal_completed": 0})["portal_completed"]

_backend = MemoryBackend()
def enabled(): return _backend.enabled
async def init(): log.info("Data storage persistence systems loaded online.")
async def upsert_member(tid: int, name: str): await _backend.upsert_member(tid, name)
async def record_anthem_complete(tid: int, lang: str): await _backend.anthem_complete(tid, lang)
async def member_state(tid: int): return await _backend.member_state(tid)
async def advance_progress(tid: int, sec: int): return await _backend.advance(tid, sec)
