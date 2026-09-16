import hashlib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from handoff import Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "handoff.db"
        self.store = Store(self.path)
        self.addCleanup(self.store.close)
        self.thread = self.store.create_thread("Fix", "Fix sessions")["id"]

    def checkpoint(self, covered):
        return self.store.checkpoint(
            self.thread, covers_through_event=covered,
            interruption_point="Code saved", next_action="Run tests",
        )

    def test_resume_without_checkpoint_and_thread_isolation(self):
        event = self.store.record(self.thread, "progress", "Investigating")
        other = self.store.create_thread("Other", "Other task")["id"]
        self.store.record(other, "progress", "Unrelated")
        result = self.store.resume(self.thread)
        self.assertIsNone(result["checkpoint"])
        self.assertEqual(result["events"], [event])
        self.assertEqual(self.store.get_event(event["id"]), event)

    def test_persistence_latest_checkpoint_and_later_events(self):
        self.store.record(self.thread, "progress", "Found bug")
        first = self.checkpoint(1)
        event = self.store.record(self.thread, "validation", "Tests passed")
        # A checkpoint prepared before event 2 must not hide that event.
        latest = self.checkpoint(1)
        with Store(self.path) as reopened:
            result = reopened.resume(self.thread)
            self.assertEqual(result["checkpoint"], latest)
            self.assertEqual(result["events"], [event])
            self.assertEqual(reopened.get_checkpoint(first["id"]), first)
        self.checkpoint(2)
        self.assertEqual(self.store.resume(self.thread)["events"], [])

    def test_correction_is_atomic_and_resume_uses_current_thread(self):
        with patch.object(self.store, "_record", side_effect=RuntimeError("Interrupted")):
            with self.assertRaises(RuntimeError):
                self.store.update_thread(self.thread, summary="Changed", objective="New")
        self.assertEqual(self.store.get_thread(self.thread)["objective"], "Fix sessions")
        self.store.update_thread(self.thread, summary="User correction", objective="New")
        result = self.store.resume(self.thread)
        self.assertEqual(result["thread"]["objective"], "New")
        self.assertEqual(result["events"][0]["type"], "correction")

    def test_artifact_persistence_and_evidence_ownership(self):
        path = Path(self.temp.name) / "test.log"
        path.write_bytes(b"passed")
        artifact = self.store.add_artifact(self.thread, path, "text/plain")
        self.assertEqual(artifact["sha256"], hashlib.sha256(b"passed").hexdigest())
        self.store.record(self.thread, "validation", "Passed", [artifact["id"]])
        with Store(self.path) as reopened:
            self.assertEqual(reopened.get_artifact(artifact["id"]), artifact)
        other = self.store.create_thread("Other", "Other")["id"]
        with self.assertRaises(ValueError):
            self.store.record(other, "validation", "Wrong evidence", [artifact["id"]])
        with self.assertRaises(KeyError):
            self.store.record(self.thread, "validation", "Missing evidence", ["missing"])
        self.assertEqual(len(self.store.resume(self.thread)["events"]), 1)

    def test_invalid_coverage_and_missing_thread(self):
        with self.assertRaises(ValueError):
            self.checkpoint(1)
        self.store.record(self.thread, "progress", "Done")
        self.checkpoint(1)
        with self.assertRaises(ValueError):
            self.checkpoint(0)
        with self.assertRaises(KeyError):
            self.store.resume("missing")
        with self.assertRaises(ValueError):
            self.store.update_thread(self.thread, summary="Bad", status="unknown")

    def test_concurrent_event_sequences(self):
        def write(index):
            with Store(self.path) as store:
                return store.record(self.thread, "progress", str(index))["sequence"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            sequences = list(pool.map(write, range(12)))
        self.assertEqual(sorted(sequences), list(range(1, 13)))


if __name__ == "__main__":
    unittest.main()
