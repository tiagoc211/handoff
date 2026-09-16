import asyncio
import sys
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ServerTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def client(self, directory):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "handoff.server", "--db", str(Path(directory) / "test.db")],
            cwd=directory,  # Installed package must work outside the repository.
        )
        async with asyncio.timeout(30):
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    initialization = await session.initialize()
                    self.assertTrue(initialization.instructions)
                    yield session

    async def call(self, session, name, **arguments):
        result = await session.call_tool(name, arguments)
        self.assertFalse(result.isError, result.content)
        self.assertIsNotNone(result.structuredContent)
        return result.structuredContent

    async def test_handoff_survives_new_server_process(self):
        with tempfile.TemporaryDirectory() as directory:
            async with self.client(directory) as client:
                listed = await client.list_tools()
                self.assertEqual({t.name for t in listed.tools},
                                 {"start", "record", "checkpoint", "resume", "read"})
                thread = await self.call(client, "start", title="Fix", objective="Fix bug")
                tid = thread["id"]
                empty = await self.call(client, "resume", thread_id=tid)
                self.assertIsNone(empty["checkpoint"])
                event = await self.call(client, "record", thread_id=tid,
                                        event_type="progress", summary="Bug located")
                checkpoint = await self.call(
                    client, "checkpoint", thread_id=tid, covers_through_event=event["sequence"],
                    interruption_point="Before editing", next_action="Apply fix",
                )
                await self.call(client, "record", thread_id=tid, event_type="correction",
                                summary="User clarified", changes={"constraints": ["Use dev"]})
            async with self.client(directory) as client:
                resumed = await self.call(client, "resume", thread_id=tid)
                self.assertEqual(resumed["checkpoint"], checkpoint)
                self.assertEqual(resumed["thread"]["constraints"], ["Use dev"])
                self.assertEqual([e["sequence"] for e in resumed["events"]], [2])
                stored = await self.call(client, "read", kind="event", record_id=event["id"])
                self.assertEqual(stored, event)

    async def test_evidence_paging_integrity_and_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "result.txt"
            log.write_text("abcdef", encoding="utf-8")
            async with self.client(directory) as client:
                thread = await self.call(client, "start", title="Test", objective="Test")
                tid = thread["id"]
                artifact = await self.call(client, "record", thread_id=tid,
                                          event_type="artifact", artifact_path=str(log))
                await self.call(client, "record", thread_id=tid, event_type="validation",
                                summary="Passed", evidence_refs=[artifact["id"]])
                metadata = await self.call(client, "read", kind="artifact", record_id=artifact["id"])
                self.assertNotIn("content", metadata)
                page = await self.call(client, "read", kind="artifact", record_id=artifact["id"],
                                       include_content=True, limit=3)
                self.assertEqual(page["content"], "abc")
                page = await self.call(client, "read", kind="artifact", record_id=artifact["id"],
                                       include_content=True, offset=page["next_offset"], limit=3)
                self.assertEqual(page["content"], "def")
                self.assertIsNone(page["next_offset"])
                log.write_text("changed", encoding="utf-8")
                errors = [
                    ("read", {"kind": "artifact", "record_id": artifact["id"], "include_content": True}),
                    ("resume", {"thread_id": "missing"}),
                    ("record", {"thread_id": tid, "event_type": "invalid"}),
                    ("record", {"thread_id": tid, "event_type": "correction", "summary": "Bad",
                                "changes": {"status": "invalid"}}),
                    ("checkpoint", {"thread_id": tid, "covers_through_event": 99,
                                    "interruption_point": "Stopped", "next_action": "Continue"}),
                ]
                for name, args in errors:
                    result = await client.call_tool(name, args)
                    self.assertTrue(result.isError, (name, result))
                resumed = await self.call(client, "resume", thread_id=tid)
                self.assertEqual(len(resumed["events"]), 1)
                self.assertIsNone(resumed["checkpoint"])
