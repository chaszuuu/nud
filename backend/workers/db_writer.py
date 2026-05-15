# backend/workers/db_writer.py
import asyncio
import logging
import multiprocessing as mp
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

OP_UPSERT_CONTENT = "upsert_content"
OP_UPSERT_HISTORY = "upsert_history"
OP_SHUTDOWN       = "shutdown"

BATCH_SIZE     = 50
FLUSH_INTERVAL = 5.0
MAX_QUEUE_SIZE = 1000


class DBWriter:

    def __init__(self, db_url: str, queue: mp.Queue):
        self.db_url = db_url
        self.queue  = queue
        self._buffer: list[dict] = []
        self._engine = None
        self._session_factory = None

    def _init_db(self):
        from models.base import Base
        from models.user import User
        from models.content import Content
        from models.history import WatchHistory

        self._engine = create_async_engine(
            self.db_url,
            poolclass=NullPool,
            echo=False,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def _flush(self):
        if not self._buffer:
            return

        batch = self._buffer[:]
        self._buffer.clear()

        async with self._session_factory() as session:
            try:
                for item in batch:
                    op = item.get("op")
                    if op == OP_UPSERT_CONTENT:
                        await self._upsert_content(session, item["data"])
                    elif op == OP_UPSERT_HISTORY:
                        await self._upsert_history(session, item["data"])

                await session.commit()
                logger.debug(f"Flushed {len(batch)} records")

            except Exception as e:
                await session.rollback()
                logger.error(f"Flush failed: {e}")
                for failed in batch:
                    if failed.get("retries", 0) < 2:
                        failed["retries"] = failed.get("retries", 0) + 1
                        try:
                            self.queue.put_nowait(failed)
                        except Exception:
                            pass

    async def _upsert_content(self, session: AsyncSession, data: dict):
        from models.history import WatchHistory
        from models.content import Content
        from sqlalchemy import update

        if set(data.keys()) <= {"id", "source_site", "source_slug"}:
            await session.execute(
                update(Content)
                .where(Content.id == data["id"])
                .values(
                    source_site=data.get("source_site"),
                    source_slug=data.get("source_slug"),
                )
            )
            return

        stmt = pg_insert(Content).values(**data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["tmdb_id"],
            set_={
                "title":       stmt.excluded.title,
                "overview":    stmt.excluded.overview,
                "poster_path": stmt.excluded.poster_path,
                "rating":      stmt.excluded.rating,
                "source_slug": stmt.excluded.source_slug,
                "source_site": stmt.excluded.source_site,
            }
        )
        await session.execute(stmt)

    async def _upsert_history(self, session: AsyncSession, data: dict):
        from models.content import Content
        from models.user import User
        from models.history import WatchHistory

        stmt = pg_insert(WatchHistory).values(**data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "content_id", "episode", "season"],
            set_={
                "progress":   stmt.excluded.progress,
                "completed":  stmt.excluded.completed,
                "watched_at": datetime.now(timezone.utc),
            }
        )
        await session.execute(stmt)

    async def _drain_queue(self):
        while True:
            try:
                item = self.queue.get_nowait()
                if item.get("op") == OP_SHUTDOWN:
                    return False
                self._buffer.append(item)
                if len(self._buffer) >= BATCH_SIZE:
                    await self._flush()
            except Exception:
                break
        return True

    async def run(self):
        self._init_db()
        logger.info("DB writer started")

        try:
            while True:
                keep_running = await self._drain_queue()
                await self._flush()

                if not keep_running:
                    logger.info("DB writer shutting down")
                    break

                await asyncio.sleep(FLUSH_INTERVAL)
        finally:
            if self._engine:
                await self._engine.dispose()


def start_writer_process(db_url: str, queue: mp.Queue):
    writer = DBWriter(db_url, queue)
    asyncio.run(writer.run())


_writer_queue: mp.Queue = None
_writer_process: mp.Process = None


def init_writer(db_url: str):
    global _writer_queue, _writer_process
    _writer_queue = mp.Queue(maxsize=MAX_QUEUE_SIZE)
    _writer_process = mp.Process(
        target=start_writer_process,
        args=(db_url, _writer_queue),
        daemon=True,
        name="nud-db-writer",
    )
    _writer_process.start()
    logger.info(f"DB writer process started — PID {_writer_process.pid}")


def stop_writer():
    global _writer_queue, _writer_process
    if _writer_queue:
        try:
            _writer_queue.put_nowait({"op": OP_SHUTDOWN})
        except Exception:
            pass
    if _writer_process and _writer_process.is_alive():
        _writer_process.join(timeout=10)
        if _writer_process.is_alive():
            _writer_process.kill()
            logger.warning("DB writer force killed")


def enqueue_content(data: dict):
    if _writer_queue:
        try:
            _writer_queue.put_nowait({"op": OP_UPSERT_CONTENT, "data": data})
        except Exception:
            logger.warning("DB writer queue full — content write dropped")


def enqueue_history(data: dict):
    if _writer_queue:
        try:
            _writer_queue.put_nowait({"op": OP_UPSERT_HISTORY, "data": data})
        except Exception:
            logger.warning("DB writer queue full — history write dropped")