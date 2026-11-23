import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

import scripts.kill_switch as ks


class KillSwitchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        ks.SWITCH_PATH = root / ".channel_kill_switch.json"
        ks.RUN_STATUS_PATH = root / "logs" / "run_status.json"

    def test_default_not_blocked(self):
        self.assertFalse(ks.is_blocked())
        state = ks.read_state()
        self.assertFalse(state["active"])

    def test_block_and_clear(self):
        state = ks.block("strike tespit edildi")
        self.assertTrue(state["active"])
        self.assertTrue(ks.is_blocked())
        self.assertTrue(ks.RUN_STATUS_PATH.exists())
        run_status = __import__("json").loads(ks.RUN_STATUS_PATH.read_text())
        self.assertEqual(run_status["status"], "blocked")

        cleared = ks.clear()
        self.assertFalse(cleared["active"])
        self.assertFalse(ks.is_blocked())

    def test_gate_output_format(self):
        ks.block("test")
        sys.argv = ["kill_switch.py", "gate"]
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ks.main()
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("proceed=false", out)

        ks.clear()
        buf = io.StringIO()
        with redirect_stdout(buf):
            ks.main()
        self.assertIn("proceed=true", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
