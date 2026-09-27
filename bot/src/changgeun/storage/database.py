"""SQLite connections, checksum-verified migrations and consistent backups."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from changgeun.domain.models import DomainError


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()
        self.path.chmod(0o600)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        migrations = [
            (int(p.name.split("_", 1)[0]), p.read_text())
            for p in sorted((Path(__file__).parent / "migrations").glob("*.sql"))
        ]
        checksums = {
            version: hashlib.sha256(sql.encode()).hexdigest() for version, sql in migrations
        }
        with self.transaction() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if tables:
                if "schema_migrations" not in {r[0] for r in tables}:
                    raise DomainError("unknown_database_schema")
                rows = conn.execute("SELECT version,checksum FROM schema_migrations").fetchall()
                applied = {r[0]: r[1] for r in rows}
                if set(applied) != set(range(1, len(applied) + 1)) or any(
                    checksums.get(version) != checksum for version, checksum in applied.items()
                ):
                    raise DomainError("migration_checksum_mismatch")
            else:
                applied = {}
            # executescript commits implicitly: execute each statement inside our transaction.
            for version, sql in migrations:
                if version in applied:
                    continue
                for statement in sql.split(";"):
                    if statement.strip():
                        conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations VALUES(?,?)", (version, checksums[version])
                )

    def ensure_guild(self, guild_id: str) -> None:
        with self.transaction() as conn:
            conn.execute("INSERT OR IGNORE INTO guild_settings(guild_id) VALUES(?)", (guild_id,))
            conn.execute("INSERT OR IGNORE INTO sessions(guild_id) VALUES(?)", (guild_id,))

    def backup(self, destination: str | Path) -> None:
        destination = Path(destination)
        if destination.exists() or destination.resolve() == self.path.resolve():
            raise DomainError("backup_destination_exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = self.connect()
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise DomainError("backup_integrity_failed")
        finally:
            source.close()
            target.close()
        destination.chmod(0o600)
