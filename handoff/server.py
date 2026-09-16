"""MCP stdio adapter over the SQLite store."""

import argparse
import hashlib
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict

from .storage import Store


class ThreadChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    objective: str | None = None
    acceptance_criteria: list[str] | None = None
    constraints: list[str] | None = None
    status: Literal["active", "blocked", "completed"] | None = None


def create_server(database: str) -> FastMCP:
    server = FastMCP(
        "handoff",
        instructions=(
            "Start a thread once; save its ID. Record meaningful progress and corrections. "
            "Checkpoint before stopping, using the last event sequence you actually read. "
            "Resume by ID and read evidence only when needed. Confirm workspace state "
            "before trusting past validations."
        ),
        log_level="WARNING",
    )

    @server.tool()
    def start(title: str, objective: str, acceptance_criteria: list[str] | None = None,
              constraints: list[str] | None = None) -> dict[str, Any]:
        """Create a task thread. Keep its ID for future sessions."""
        with Store(database) as store:
            return store.create_thread(title, objective, acceptance_criteria, constraints)

    @server.tool()
    def record(thread_id: str,
               event_type: Literal["progress", "decision", "validation", "blocker", "correction", "artifact"],
               summary: str = "", evidence_refs: list[str] | None = None,
               changes: ThreadChanges | None = None, artifact_path: str | None = None,
               media_type: str = "text/plain") -> dict[str, Any]:
        """Record an event; correction+changes updates the thread atomically.

        artifact+artifact_path registers a local file and returns its evidence ID.
        Files must remain available. Other events can reference that ID.
        """
        with Store(database) as store:
            if event_type == "artifact":
                if not artifact_path or changes or evidence_refs:
                    raise ValueError("Artifact requires artifact_path, without changes or evidence_refs")
                if not Path(artifact_path).is_absolute():
                    raise ValueError("artifact_path must be absolute")
                return store.add_artifact(thread_id, artifact_path, media_type)
            if artifact_path:
                raise ValueError("artifact_path requires event_type=artifact")
            if not summary.strip():
                raise ValueError("An event needs a summary")
            if changes is not None:
                if event_type != "correction" or evidence_refs:
                    raise ValueError("changes requires correction without evidence_refs")
                return store.update_thread(
                    thread_id, summary=summary, **changes.model_dump(exclude_none=True)
                )
            return store.record(thread_id, event_type, summary, evidence_refs)

    @server.tool()
    def checkpoint(thread_id: str, covers_through_event: int, interruption_point: str,
                   next_action: str, completed: list[str] | None = None,
                   in_progress: list[str] | None = None, pending: list[str] | None = None,
                   decisions: list[str] | None = None, failed_approaches: list[str] | None = None,
                   workspace: dict | None = None, validations: list[dict] | None = None,
                   open_questions: list[str] | None = None) -> dict[str, Any]:
        """Save a complete work snapshot; coverage is the last event incorporated (0 if none).

        Decisions and failed approaches include reasons. Validations include check,
        result, tested state and evidence reference. Do not copy large logs here.
        """
        with Store(database) as store:
            return store.checkpoint(
                thread_id, covers_through_event=covers_through_event,
                interruption_point=interruption_point, next_action=next_action,
                completed=completed, in_progress=in_progress, pending=pending,
                decisions=decisions, failed_approaches=failed_approaches,
                workspace=workspace, validations=validations, open_questions=open_questions,
            )

    @server.tool()
    def resume(thread_id: str) -> dict[str, Any]:
        """Return current thread, latest checkpoint and only events after its coverage."""
        with Store(database) as store:
            return store.resume(thread_id)

    @server.tool()
    def read(kind: Literal["thread", "event", "checkpoint", "artifact"], record_id: str,
             include_content: bool = False, offset: int = 0, limit: int = 4000) -> dict[str, Any]:
        """Read a record by ID. Artifact text is opt-in, hash-checked and paged in characters."""
        if offset < 0 or not 1 <= limit <= 16000:
            raise ValueError("offset must be nonnegative; limit must be 1..16000")
        if include_content and kind != "artifact":
            raise ValueError("include_content is only supported for artifacts")
        with Store(database) as store:
            result = getattr(store, f"get_{kind}")(record_id)
        if include_content:
            content = Path(result["location"]).read_bytes()
            if hashlib.sha256(content).hexdigest() != result["sha256"]:
                raise ValueError("Artifact changed since registration; register its new version")
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Artifact is not UTF-8 text; use its file location") from exc
            end = offset + limit
            result.update(content=text[offset:end],
                          next_offset=end if end < len(text) else None)
        return result

    return server


def main():
    parser = argparse.ArgumentParser(description="Handoff MCP server (stdio)")
    parser.add_argument("--db", default="handoff.db", help="SQLite file (prefer an absolute path)")
    args = parser.parse_args()
    create_server(str(Path(args.db).resolve())).run(transport="stdio")


if __name__ == "__main__":
    main()
