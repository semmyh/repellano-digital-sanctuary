"""
Member records: who has finished the Anthem and how far each member has read in the portal.

Uses a free Neon Postgres database when DATABASE_URL is set. Without it (or without the
`asyncpg` package) the bot keeps working exactly as before: the portal falls back to
Telegram's own storage, and nothing is saved on our side.
"""
import os
import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

log = logging.getLogger("repellano.db")

TOTAL_SECTIONS = 6

try:
    import asyncpg
except Exception:  # package not installed
    asyncpg = None


def _clean_dsn(dsn: str) -> str:
    """Neon adds channel_binding=require, which asyncpg does not understand; drop it."""
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
    "CREATE INDEX IF NOT EXISTS events_member_idx ON events (telegram_id, at)",
]


# ---------------------------------------------------------------- backends
class MemoryBackend:
    """Used when no database is configured (also handy for tests). Forgets everything on restart."""
    enabled = False

    def __init__(self):
        self.members: dict[int, dict] = {}
        self.events: list[tuple] = []

    def _m(self, tid):
        return self.members.setdefault(tid, {"first_name": None, "anthem_lang": None,
                                             "anthem_done": False, "portal_completed": 0})

    async def upsert_member(self, tid, first_name):
        self._m(tid)["first_name"] = first_name

    async def anthem_complete(self, tid, lang):
        m = self._m(tid); m["anthem_lang"] = lang; m["anthem_done"] = True

    async def get_progress(self, tid):
        return self._m(tid)["portal_completed"]

    async def advance(self, tid, section):
        m = self._m(tid)
        if m["portal_completed"] == section and section < TOTAL_SECTIONS:
            m["portal_completed"] += 1
        return m["portal_completed"]

    async def reset(self, tid):
        self.members[tid] = {"first_name": None, "anthem_lang": None, "anthem_done": False, "portal_completed": 0}

    async def log_event(self, tid, event, detail):
        self.events.append((tid, event, detail))


class PgBackend:
    enabled = True

    def __init__(self, pool):
        self.pool = pool

    async def _run(self, fn):
        """Run a query; retry when Neon has just woken up or dropped an idle connection."""
        last = None
        for attempt in range(3):
            try:
                async with self.pool.acquire() as con:
                    return await fn(con)
            except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError, OSError, ConnectionError) as e:
                last = e
                await asyncio.sleep(0.6 * (attempt + 1))
        raise last

    async def upsert_member(self, tid, first_name):
        async def f(con):
            await con.execute(
                "INSERT INTO members (telegram_id, first_name) VALUES ($1, $2) "
                "ON CONFLICT (telegram_id) DO UPDATE SET first_name = EXCLUDED.first_name, updated_at = now()",
                tid, first_name)
        await self._run(f)

    async def anthem_complete(self, tid, lang):
        async def f(con):
            await con.execute(
                "INSERT INTO members (telegram_id, anthem_lang, anthem_completed_at) VALUES ($1, $2, now()) "
                "ON CONFLICT (telegram_id) DO UPDATE SET anthem_lang = EXCLUDED.anthem_lang, "
                "anthem_completed_at = now(), updated_at = now()", tid, lang)
        await self._run(f)

    async def get_progress(self, tid):
        async def f(con):
            v = await con.fetchval("SELECT portal_completed FROM members WHERE telegram_id = $1", tid)
            return int(v or 0)
        return await self._run(f)

    async def advance(self, tid, section):
        async def f(con):
            await con.execute("INSERT INTO members (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", tid)
            row = await con.fetchrow(
                "UPDATE members SET portal_completed = portal_completed + 1, "
                "portal_completed_at = CASE WHEN portal_completed + 1 >= $3 THEN now() ELSE portal_completed_at END, "
                "updated_at = now() "
                "WHERE telegram_id = $1 AND portal_completed = $2 AND portal_completed < $3 "
                "RETURNING portal_completed", tid, section, TOTAL_SECTIONS)
            if row:
                return int(row["portal_completed"])
            v = await con.fetchval("SELECT portal_completed FROM members WHERE telegram_id = $1", tid)
            return int(v or 0)
        return await self._run(f)

    async def reset(self, tid):
        async def f(con):
            await con.execute(
                "UPDATE members SET portal_completed = 0, portal_completed_at = NULL, anthem_lang = NULL, "
                "anthem_completed_at = NULL, updated_at = now() WHERE telegram_id = $1", tid)
        await self._run(f)

    async def log_event(self, tid, event, detail):
        async def f(con):
            await con.execute("INSERT INTO events (telegram_id, event, detail) VALUES ($1, $2, $3)",
                              tid, event, detail)
        await self._run(f)


_backend = MemoryBackend()


def enabled() -> bool:
    return _backend.enabled


async def init() -> None:
    """Connect to the database (if configured) and create the tables."""
    global _backend
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        log.info("DATABASE_URL not set: member records are switched off.")
        return
    if asyncpg is None:
        log.error("DATABASE_URL is set but the 'asyncpg' package is missing. Add 'asyncpg' to requirements.txt.")
        return
    try:
        pool = await asyncpg.create_pool(
            _clean_dsn(dsn), min_size=1, max_size=5, timeout=30, command_timeout=20,
            statement_cache_size=0,                 # works with Neon's pooled connections
            max_inactive_connection_lifetime=30,    # drop idle connections before Neon suspends
        )
        async with pool.acquire() as con:
            for statement in SCHEMA:
                await con.execute(statement)
        _backend = PgBackend(pool)
        log.info("Database connected: member records are ON.")
    except Exception:
        log.exception("Could not connect to the database; continuing without member records.")


# ---------------------------------------------------------------- public helpers
async def upsert_member(tid: int, first_name: str | None) -> None:
    await _backend.upsert_member(tid, first_name)


async def record_anthem_complete(tid: int, lang: str | None) -> None:
    await _backend.anthem_complete(tid, lang)
    await _backend.log_event(tid, "anthem_completed", lang)


async def get_progress(tid: int) -> int:
    return await _backend.get_progress(tid)


async def advance_progress(tid: int, section: int) -> int:
    """The member has read section number `section` (0-based). Moves progress forward by one
    only if that is exactly the next section, so nobody can skip ahead. Returns the new count."""
    before = await _backend.get_progress(tid)
    after = await _backend.advance(tid, section)
    if after > before:
        await _backend.log_event(tid, "section_read", str(section + 1))
    return after


async def reset_member(tid: int) -> None:
    await _backend.reset(tid)
    await _backend.log_event(tid, "reset", None)


async def safe(coro) -> None:
    """Run a database action in the background without ever breaking the bot."""
    try:
        await coro
    except Exception:
        log.exception("Database action failed (ignored)")
