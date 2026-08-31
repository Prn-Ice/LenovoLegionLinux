import contextlib
import io
import json
import unittest

from legion_linux import legion
from legion_linux import legion_cli


class FakeGraphicsMode:
    DISCRETE = "discrete"
    HYBRID_IGPU_ONLY = "hybrid-igpu-only"
    HYBRID_AUTO = "hybrid-auto"

    def __init__(self):
        self.selected = "hybrid"
        self.result = {
            "schema_version": 1,
            "selected_mode": "hybrid",
            "effective_dgpu_state": "attached",
            "expected_dgpu_state": "attached",
            "available_modes": ["hybrid", "hybrid-igpu-only", "hybrid-auto", "discrete"],
            "reconciliation": "settled",
            "client_inspection_complete": True,
            "active_clients": [],
        }
        self.error = None

    def exists(self):
        return True

    def get(self):
        return self.selected

    def status(self):
        return dict(self.result)

    def set(self, mode):
        if self.error:
            raise self.error
        self.selected = mode
        result = dict(self.result)
        result["selected_mode"] = mode
        return result

    def reconcile(self):
        return dict(self.result)


class FakeLegion:
    def __init__(self):
        self.graphics_mode = FakeGraphicsMode()


class GraphicsModeCLITest(unittest.TestCase):
    def setUp(self):
        self.legion = FakeLegion()

    @staticmethod
    def capture(function, *args, **kwargs):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = function(*args, **kwargs)
        return result, output.getvalue().strip()

    def test_status_keeps_selected_mode_output_for_compatibility(self):
        result, output = self.capture(legion_cli.graphics_mode_status, self.legion)

        self.assertEqual(0, result)
        self.assertEqual("hybrid", output)

    def test_status_json_exposes_selected_and_effective_state(self):
        result, output = self.capture(legion_cli.graphics_mode_status, self.legion, json_output=True)

        self.assertEqual(0, result)
        payload = json.loads(output)
        self.assertEqual("hybrid", payload["selected_mode"])
        self.assertEqual("attached", payload["effective_dgpu_state"])

    def test_set_returns_busy_exit_code(self):
        self.legion.graphics_mode.error = legion.GraphicsModeBusyError(
            [{"pid": 2903, "comm": "code", "devices": ["/dev/nvidiactl"]}],
            True,
        )

        result, output = self.capture(
            legion_cli.graphics_mode_set,
            self.legion,
            "hybrid-igpu-only",
        )

        self.assertEqual(2, result)
        self.assertIn("code (PID 2903)", output)

    def test_set_returns_pending_exit_code(self):
        self.legion.graphics_mode.result["reconciliation"] = "needed"

        result, _ = self.capture(
            legion_cli.graphics_mode_set,
            self.legion,
            "hybrid-igpu-only",
            json_output=True,
        )

        self.assertEqual(3, result)

    def test_set_returns_pending_exit_code_after_reconciliation_error(self):
        self.legion.graphics_mode.error = legion.GraphicsModeReconciliationError("selector accepted")

        result, output = self.capture(
            legion_cli.graphics_mode_set,
            self.legion,
            "hybrid-igpu-only",
        )

        self.assertEqual(3, result)
        self.assertEqual("selector accepted", output)


if __name__ == "__main__":
    unittest.main()
