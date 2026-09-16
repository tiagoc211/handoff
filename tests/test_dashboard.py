import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from handoff import Store
from handoff.dashboard import detail


class DashboardTests(unittest.TestCase):
    def test_snapshot_and_detail_show_saved_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "handoff.db"
            with Store(path) as store:
                thread = store.create_thread("Corrigir sessões", "Rejeitar sessões expiradas")
                store.checkpoint(thread["id"], covers_through_event=0,
                                 interruption_point="Correção guardada",
                                 next_action="Executar testes", completed=["Causa identificada"])
                store.record(thread["id"], "blocker", "Ambiente indisponível")
                store.update_thread(thread["id"], summary="Bloqueio", status="blocked")
                rendered = detail(store.resume(thread["id"]), 80)
            output = subprocess.run(
                [sys.executable, "-m", "handoff.dashboard", "--db", str(path), "--once"],
                capture_output=True, text=True, check=True,
            ).stdout
            self.assertIn("Bloqueada: 1", output)
            self.assertIn(thread["id"], output)
            self.assertIn("Executar testes", rendered)
            self.assertIn("Ambiente indisponível", rendered)
            self.assertIn("Causa identificada", rendered)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.db"
            result = subprocess.run(
                [sys.executable, "-m", "handoff.dashboard", "--db", str(path), "--once"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("não encontrada", result.stderr)
            self.assertFalse(path.exists())
