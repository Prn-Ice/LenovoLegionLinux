import os
import tempfile
import unittest
from unittest.mock import patch

from legion_linux import legion


class FakeGraphicsTopology:
    def __init__(self):
        self.effective = "attached"
        self.power = "ac"
        self.clients = []
        self.inspection_complete = True

    def effective_state(self):
        return self.effective

    def power_state(self):
        return self.power

    def expected_state(self, selected_mode):
        if selected_mode in ("hybrid", "discrete"):
            return "attached"
        if selected_mode == "hybrid-igpu-only":
            return "detached"
        if selected_mode == "hybrid-auto":
            return {"ac": "attached", "battery": "detached"}.get(self.power, "unknown")
        return "unknown"

    def active_clients(self):
        return self.clients, self.inspection_complete


class GraphicsModeFeatureTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.files = {
            "gsync": "1",
            "issupportgsync": "2",
            "igpumode": "0",
            "issupportigpumode": "3",
        }
        for name, value in self.files.items():
            with open(os.path.join(self.temp_dir.name, name), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
                filepointer.write(value)

        self.path_patch = patch.object(legion, "LEGION_SYS_BASEPATH", self.temp_dir.name)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.topology = FakeGraphicsTopology()
        self.notifications = []

        def notify(available):
            self.notifications.append(available)
            selected = self.feature.get()
            if selected == "hybrid-igpu-only":
                self.topology.effective = "detached"
            elif selected in ("hybrid", "discrete"):
                self.topology.effective = "attached"
            elif selected == "hybrid-auto":
                self.topology.effective = "attached" if self.topology.power == "ac" else "detached"

        self.feature = legion.GraphicsModeFeature(
            legion.GsyncFeature(),
            topology=self.topology,
            sleep=lambda _: None,
            notify_writer=notify,
            reconcile_delay=0,
        )

    def read(self, name):
        with open(os.path.join(self.temp_dir.name, name), "r", encoding=legion.DEFAULT_ENCODING) as filepointer:
            return filepointer.read()

    def write(self, name, value):
        with open(os.path.join(self.temp_dir.name, name), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
            filepointer.write(str(value))

    def test_reports_combined_mode_and_choices(self):
        self.assertEqual("hybrid", self.feature.get())
        self.assertEqual(["hybrid", "hybrid-igpu-only", "hybrid-auto", "discrete"], self.feature.choices())

        self.write("igpumode", 1)
        self.assertEqual("hybrid-igpu-only", self.feature.get())

        self.write("igpumode", 2)
        self.assertEqual("hybrid-auto", self.feature.get())

        self.write("gsync", 0)
        self.assertEqual("discrete", self.feature.get())

    def test_applies_safe_transition_order_and_readback(self):
        self.feature.set("hybrid-igpu-only")
        self.assertEqual("1", self.read("gsync"))
        self.assertEqual("1", self.read("igpumode"))

        self.feature.set("discrete")
        self.assertEqual("0", self.read("gsync"))
        self.assertEqual("0", self.read("igpumode"))

    def test_rolls_back_first_write_when_second_write_fails(self):
        self.write("gsync", 0)

        def fail_igpu_write(_):
            raise IOError("injected failure")

        self.feature.igpu_mode.set = fail_igpu_write

        with self.assertRaisesRegex(IOError, "injected failure"):
            self.feature.set("hybrid-igpu-only")

        self.assertEqual("0", self.read("gsync"))
        self.assertEqual("0", self.read("igpumode"))

    def test_reports_rollback_readback_failure(self):
        self.write("gsync", 0)
        write_gsync = self.feature.gsync.set

        def ignore_gsync_rollback(value):
            if value:
                write_gsync(value)

        def fail_igpu_write(_):
            raise IOError("injected failure")

        self.feature.gsync.set = ignore_gsync_rollback
        self.feature.igpu_mode.set = fail_igpu_write

        with self.assertRaisesRegex(IOError, "rollback also failed"):
            self.feature.set("hybrid-igpu-only")

        self.assertEqual("1", self.read("gsync"))

    def test_rejects_unknown_firmware_mode(self):
        self.write("igpumode", 9)
        with self.assertRaisesRegex(ValueError, "invalid iGPU mode 9"):
            self.feature.get()

    def test_reports_selected_policy_separately_from_effective_topology(self):
        self.write("igpumode", 1)
        self.topology.clients = [{"pid": 2903, "comm": "code", "devices": ["/dev/nvidiactl"]}]

        status = self.feature.status()

        self.assertEqual("hybrid-igpu-only", status["selected_mode"])
        self.assertEqual("attached", status["effective_dgpu_state"])
        self.assertEqual("detached", status["expected_dgpu_state"])
        self.assertEqual("blocked", status["reconciliation"])

    def test_blocks_active_client_before_writing_selector(self):
        self.topology.clients = [{"pid": 2903, "comm": "code", "devices": ["/dev/nvidiactl"]}]

        with self.assertRaisesRegex(legion.GraphicsModeBusyError, r"code \(PID 2903\)"):
            self.feature.set("hybrid-igpu-only")

        self.assertEqual("0", self.read("igpumode"))
        self.assertEqual([], self.notifications)

    def test_blocks_incomplete_client_inspection_before_writing_selector(self):
        self.topology.inspection_complete = False

        with self.assertRaisesRegex(legion.GraphicsModeBusyError, "inspection is incomplete"):
            self.feature.set("hybrid-igpu-only")

        self.assertEqual("0", self.read("igpumode"))

    def test_setting_selected_policy_reconciles_with_observed_availability(self):
        self.write("igpumode", 1)

        result = self.feature.set("hybrid-igpu-only")

        self.assertEqual([True], self.notifications)
        self.assertEqual("detached", result["effective_dgpu_state"])
        self.assertEqual("settled", result["reconciliation"])

    def test_reconciliation_timeout_keeps_selected_policy(self):
        self.feature = legion.GraphicsModeFeature(
            legion.GsyncFeature(),
            topology=self.topology,
            sleep=lambda _: None,
            notify_writer=self.notifications.append,
            reconcile_attempts=2,
            reconcile_delay=0,
        )

        result = self.feature.set("hybrid-igpu-only")

        self.assertEqual("1", self.read("igpumode"))
        self.assertEqual([True, True], self.notifications)
        self.assertEqual("needed", result["reconciliation"])

    def test_notify_failure_keeps_selected_policy(self):
        def fail_notify(_):
            raise IOError("injected notify failure")

        self.feature = legion.GraphicsModeFeature(
            legion.GsyncFeature(),
            topology=self.topology,
            sleep=lambda _: None,
            notify_writer=fail_notify,
            reconcile_delay=0,
        )

        with self.assertRaisesRegex(legion.GraphicsModeReconciliationError, "was selected"):
            self.feature.set("hybrid-igpu-only")

        self.assertEqual("1", self.read("igpumode"))

    def test_auto_on_ac_does_not_require_ejection_preflight(self):
        self.topology.clients = [{"pid": 2903, "comm": "code", "devices": ["/dev/nvidiactl"]}]

        result = self.feature.set("hybrid-auto")

        self.assertEqual("2", self.read("igpumode"))
        self.assertEqual("settled", result["reconciliation"])

    def test_auto_on_battery_requires_ejection_preflight(self):
        self.topology.power = "battery"
        self.topology.clients = [{"pid": 2903, "comm": "code", "devices": ["/dev/nvidiactl"]}]

        with self.assertRaises(legion.GraphicsModeBusyError):
            self.feature.set("hybrid-auto")

        self.assertEqual("0", self.read("igpumode"))

    def test_auto_with_unknown_power_fails_closed(self):
        self.topology.power = "unknown"

        with self.assertRaisesRegex(legion.GraphicsModePowerStateError, "power state is unknown"):
            self.feature.set("hybrid-auto")

        self.assertEqual("0", self.read("igpumode"))

    def test_client_appearing_after_preflight_rolls_back_raw_state(self):
        calls = 0

        def active_clients():
            nonlocal calls
            calls += 1
            if calls == 1:
                return [], True
            return [{"pid": 2903, "comm": "code", "devices": ["/dev/nvidiactl"]}], True

        self.topology.active_clients = active_clients

        with self.assertRaises(legion.GraphicsModeBusyError):
            self.feature.set("hybrid-igpu-only")

        self.assertEqual("1", self.read("gsync"))
        self.assertEqual("0", self.read("igpumode"))


class GraphicsTopologyTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.pci = os.path.join(self.temp_dir.name, "pci")
        self.power = os.path.join(self.temp_dir.name, "power")
        self.proc = os.path.join(self.temp_dir.name, "proc")
        self.dev = os.path.join(self.temp_dir.name, "dev")
        os.makedirs(self.pci)
        os.makedirs(self.power)
        os.makedirs(self.proc)
        os.makedirs(self.dev)

    def add_gpu(self, bound):
        gpu = os.path.join(self.pci, "0000:01:00.0")
        os.makedirs(gpu)
        for name, value in (("vendor", "0x10de"), ("class", "0x030000")):
            with open(os.path.join(gpu, name), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
                filepointer.write(value)
        if bound:
            driver = os.path.join(self.temp_dir.name, "driver")
            os.makedirs(driver, exist_ok=True)
            os.symlink(driver, os.path.join(gpu, "driver"))

    def test_effective_topology_distinguishes_detached_partial_and_attached(self):
        topology = legion.GraphicsTopology(pci_root=self.pci, power_root=self.power)
        self.assertEqual("detached", topology.effective_state())
        self.add_gpu(False)
        self.assertEqual("partial", topology.effective_state())
        os.symlink(self.temp_dir.name, os.path.join(self.pci, "0000:01:00.0", "driver"))
        self.assertEqual("attached", topology.effective_state())

    def test_auto_expected_state_uses_enumerated_power_supply(self):
        ac = os.path.join(self.power, "AC")
        os.makedirs(ac)
        with open(os.path.join(ac, "type"), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
            filepointer.write("Mains")
        with open(os.path.join(ac, "online"), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
            filepointer.write("0")
        topology = legion.GraphicsTopology(pci_root=self.pci, power_root=self.power)
        self.assertEqual("detached", topology.expected_state("hybrid-auto"))
        with open(os.path.join(ac, "online"), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
            filepointer.write("1")
        self.assertEqual("attached", topology.expected_state("hybrid-auto"))

    def test_battery_status_is_not_mistaken_for_external_power(self):
        battery = os.path.join(self.power, "BAT1")
        os.makedirs(battery)
        for name, value in (("type", "Battery"), ("online", "1")):
            with open(os.path.join(battery, name), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
                filepointer.write(value)

        topology = legion.GraphicsTopology(pci_root=self.pci, power_root=self.power)

        self.assertEqual("unknown", topology.power_state())

    def test_unreadable_power_supply_makes_auto_power_unknown(self):
        offline = os.path.join(self.power, "AC")
        unreadable = os.path.join(self.power, "USB-C")
        os.makedirs(offline)
        os.makedirs(unreadable)
        for name, value in (("type", "Mains"), ("online", "0")):
            with open(os.path.join(offline, name), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
                filepointer.write(value)
        with open(os.path.join(unreadable, "type"), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
            filepointer.write("USB_PD")

        topology = legion.GraphicsTopology(pci_root=self.pci, power_root=self.power)

        self.assertEqual("unknown", topology.power_state())

    def test_active_client_detection_matches_character_device_identity(self):
        os.symlink("/dev/null", os.path.join(self.dev, "nvidiactl"))
        process = os.path.join(self.proc, "2903")
        os.makedirs(os.path.join(process, "fd"))
        with open(os.path.join(process, "comm"), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
            filepointer.write("code\n")
        os.symlink(os.path.join(self.dev, "nvidiactl"), os.path.join(process, "fd", "28"))
        topology = legion.GraphicsTopology(
            pci_root=self.pci,
            power_root=self.power,
            proc_root=self.proc,
            dev_root=self.dev,
        )

        clients, complete = topology.active_clients()

        self.assertTrue(complete)
        self.assertEqual(2903, clients[0]["pid"])
        self.assertEqual("code", clients[0]["comm"])

    def test_unreadable_pci_function_makes_topology_unknown(self):
        gpu = os.path.join(self.pci, "0000:01:00.0")
        os.makedirs(gpu)
        with open(os.path.join(gpu, "vendor"), "w", encoding=legion.DEFAULT_ENCODING) as filepointer:
            filepointer.write("0x10de")

        topology = legion.GraphicsTopology(pci_root=self.pci, power_root=self.power)

        self.assertEqual("unknown", topology.effective_state())
        self.assertEqual(([], False), topology.active_clients())

    def test_missing_nvidia_drm_directory_makes_client_inspection_incomplete(self):
        self.add_gpu(True)
        os.symlink("/dev/null", os.path.join(self.dev, "nvidiactl"))
        topology = legion.GraphicsTopology(
            pci_root=self.pci,
            power_root=self.power,
            proc_root=self.proc,
            dev_root=self.dev,
        )

        _, complete = topology.active_clients()

        self.assertFalse(complete)


class GraphicsDGPUNotifyTest(unittest.TestCase):
    def test_serializes_observed_availability(self):
        with tempfile.NamedTemporaryFile(mode="r+", encoding=legion.DEFAULT_ENCODING) as notify_file:
            notifier = legion.GraphicsDGPUNotify(path=notify_file.name)

            notifier.write(True)
            notify_file.seek(0)
            self.assertEqual("1", notify_file.read())

            notifier.write(False)
            notify_file.seek(0)
            self.assertEqual("0", notify_file.read())


if __name__ == "__main__":
    unittest.main()
