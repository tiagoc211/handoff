import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "tasks.db"

    def run_cli(self, *args, data=None, ok=True):
        result = subprocess.run(
            [sys.executable, "-m", "handoff.cli", "--db", str(self.db), *args],
            input=json.dumps(data) if data is not None else None,
            capture_output=True, text=True, cwd=self.temp.name,
        )
        self.assertEqual(result.returncode, 0 if ok else 1, result.stderr)
        if not ok:
            self.assertEqual(result.stdout, "")
            return result.stderr
        return json.loads(result.stdout)

    def test_complete_handoff_across_processes(self):
        thread = self.run_cli("start", "Corrigir", "--objective", "Corrigir sessões", "--constraint", "Usar dev")
        tid = thread["id"]
        self.assertIsNone(self.run_cli("resume", tid)["checkpoint"])
        event = self.run_cli("record", tid, "Causa identificada")
        checkpoint = self.run_cli("checkpoint", tid, "--file", "-", data={
            "covers_through_event": event["sequence"],
            "interruption_point": "Antes de editar", "next_action": "Aplicar correção",
        })
        self.run_cli("update", tid, "--summary", "Clarificação", "--file", "-",
                     data={"constraints": ["Sem alterar API"]})
        resumed = self.run_cli("resume", tid)
        self.assertEqual(resumed["checkpoint"], checkpoint)
        self.assertEqual(resumed["thread"]["constraints"], ["Sem alterar API"])
        self.assertEqual([e["sequence"] for e in resumed["events"]], [2])
        self.assertEqual(self.run_cli("list")[0]["id"], tid)
        self.assertEqual(self.run_cli("read", "event", event["id"]), event)

    def test_evidence_and_invalid_input(self):
        tid = self.run_cli("start", "Teste", "--objective", "Testar")["id"]
        log = Path(self.temp.name) / "result.txt"
        log.write_text("abcdef")
        aid = self.run_cli("artifact", tid, str(log))["id"]
        self.run_cli("record", tid, "Passou", "--type", "validation", "--evidence", aid)
        page = self.run_cli("read", "artifact", aid, "--content", "--limit", "3")
        self.assertEqual(page["content"], "abc")
        self.assertEqual(page["next_offset"], 3)
        log.write_text("changed")
        self.assertIn("alterado", self.run_cli("read", "artifact", aid, "--content", ok=False))
        self.run_cli("checkpoint", tid, "--file", "-", data={
            "covers_through_event": 99, "interruption_point": "Parado", "next_action": "Testar",
        }, ok=False)
        self.run_cli("update", tid, "--summary", "Erro", "--file", "-", data={"status": "invalid"}, ok=False)
        self.assertIsNone(self.run_cli("resume", tid)["checkpoint"])
        self.assertEqual(len(self.run_cli("resume", tid)["events"]), 1)
        self.run_cli("resume", "missing", ok=False)
