"""SQLite storage; payloads use the JSON structures in docs/data-contract.md."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Store:
    def __init__(self, path="handoff.db"):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS threads (
                id TEXT PRIMARY KEY, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL REFERENCES threads(id),
                sequence INTEGER NOT NULL, data TEXT NOT NULL,
                UNIQUE(thread_id, sequence)
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                position INTEGER PRIMARY KEY,
                id TEXT NOT NULL UNIQUE,
                thread_id TEXT NOT NULL REFERENCES threads(id),
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS checkpoint_thread
                ON checkpoints(thread_id, position);
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL REFERENCES threads(id),
                data TEXT NOT NULL
            );
        """)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _insert(self, table, data, **columns):
        values = {"id": data["id"], **columns, "data": json.dumps(data)}
        names = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        self.db.execute(
            f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
            tuple(values.values()),
        )
        return data

    def _get(self, table, record_id):
        row = self.db.execute(
            f"SELECT data FROM {table} WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            raise KeyError(record_id)
        return json.loads(row[0])

    def create_thread(self, title, objective, acceptance_criteria=None, constraints=None):
        data = dict(id=uuid4().hex, title=title, objective=objective,
                    acceptance_criteria=acceptance_criteria or [],
                    constraints=constraints or [], status="active")
        with self.db:
            return self._insert("threads", data)

    def get_thread(self, thread_id):
        return self._get("threads", thread_id)

    def list_threads(self):
        rows = self.db.execute("SELECT data FROM threads ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def _last_sequence(self, thread_id):
        return self.db.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM events WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()[0]

    def _record(self, thread_id, event_type, summary, evidence_refs):
        if event_type not in {"progress", "decision", "validation", "blocker", "correction"}:
            raise ValueError("Unknown event type")
        self.get_thread(thread_id)
        for ref in evidence_refs:
            if self.get_artifact(ref)["thread_id"] != thread_id:
                raise ValueError("Evidence belongs to another thread")
        data = dict(id=uuid4().hex, thread_id=thread_id,
                    sequence=self._last_sequence(thread_id) + 1,
                    type=event_type, summary=summary, evidence_refs=evidence_refs,
                    created_at=datetime.now(timezone.utc).isoformat())
        return self._insert("events", data, thread_id=thread_id, sequence=data["sequence"])

    def record(self, thread_id, event_type, summary, evidence_refs=None):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return self._record(thread_id, event_type, summary, evidence_refs or [])

    def update_thread(self, thread_id, *, summary, **changes):
        if not changes or changes.keys() - {
            "title", "objective", "acceptance_criteria", "constraints", "status"
        }:
            raise ValueError("Provide supported thread fields")
        if "status" in changes and changes["status"] not in {"active", "blocked", "completed"}:
            raise ValueError("Unknown thread status")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            data = self.get_thread(thread_id)
            data.update(changes)
            self.db.execute("UPDATE threads SET data = ? WHERE id = ?",
                            (json.dumps(data), thread_id))
            self._record(thread_id, "correction", summary, [])
        return data

    def checkpoint(self, thread_id, *, covers_through_event, interruption_point,
                   next_action, completed=None, in_progress=None, pending=None,
                   decisions=None, failed_approaches=None, workspace=None,
                   validations=None, open_questions=None):
        # Coverage is explicit: events arriving after the agent's read stay visible.
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            thread = self.get_thread(thread_id)
            if type(covers_through_event) is not int or not (
                0 <= covers_through_event <= self._last_sequence(thread_id)
            ):
                raise ValueError("Invalid event coverage")
            previous = self._latest_checkpoint(thread_id)
            if previous and covers_through_event < previous["covers_through_event"]:
                raise ValueError("Checkpoint coverage cannot move backwards")
            if not next_action and thread["status"] == "active":
                raise ValueError("An active thread needs a next action")
            if thread["status"] == "blocked" and not open_questions:
                raise ValueError("Describe the blocker in open_questions")
            data = dict(
                id=uuid4().hex, thread_id=thread_id, schema_version=1,
                covers_through_event=covers_through_event,
                completed=completed or [], in_progress=in_progress or [],
                pending=pending or [], decisions=decisions or [],
                failed_approaches=failed_approaches or [],
                interruption_point=interruption_point, next_action=next_action,
                workspace=workspace, validations=validations or [],
                open_questions=open_questions or [],
            )
            return self._insert("checkpoints", data, thread_id=thread_id)

    def _latest_checkpoint(self, thread_id):
        row = self.db.execute(
            "SELECT data FROM checkpoints WHERE thread_id = ? ORDER BY position DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def get_checkpoint(self, checkpoint_id):
        return self._get("checkpoints", checkpoint_id)

    def get_event(self, event_id):
        return self._get("events", event_id)

    def resume(self, thread_id):
        with self.db:
            self.db.execute("BEGIN")
            thread = self.get_thread(thread_id)
            checkpoint = self._latest_checkpoint(thread_id)
            covered = checkpoint["covers_through_event"] if checkpoint else 0
            rows = self.db.execute(
                "SELECT data FROM events WHERE thread_id = ? AND sequence > ? ORDER BY sequence",
                (thread_id, covered),
            ).fetchall()
        return dict(thread=thread, checkpoint=checkpoint,
                    events=[json.loads(row[0]) for row in rows])

    def add_artifact(self, thread_id, path, media_type="application/octet-stream"):
        """Register an existing local file; the caller keeps the file available."""
        path = Path(path).resolve()
        with path.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        data = dict(id=uuid4().hex, thread_id=thread_id, media_type=media_type,
                    location=str(path), sha256=digest)
        with self.db:
            self.get_thread(thread_id)
            return self._insert("artifacts", data, thread_id=thread_id)

    def get_artifact(self, artifact_id):
        return self._get("artifacts", artifact_id)
