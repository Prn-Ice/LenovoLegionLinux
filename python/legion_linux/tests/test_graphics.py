from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from legion_linux import legion_cli
from legion_linux.graphics import GraphicsMode, Mode
from legion_linux.graphics_boot import BootSupportAction, GraphicsBoot, UNIT_NAME


class GraphicsModeTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.legion = self.root / "legion"
        self.pci = self.root / "bus/pci/devices"
        self.pci.mkdir(parents=True)
        self.graphics = GraphicsMode(legion=self.legion, sysfs=self.root, state=self.root / "state")
        self.vendor_units = self.root / "vendor"
        self.graphics.boot = GraphicsBoot(local=self.root / "local", system=(self.vendor_units,))
        root_user = patch("legion_linux.graphics.os.geteuid", return_value=0)
        root_user.start()
        self.addCleanup(root_user.stop)
        for attribute, value in {
            "issupportgsync": 2,
            "gsync": 1,
            "issupportigpumode": 3,
            "igpumode": 1,
            "notify_dgpu": 0,
        }.items():
            self.write(self.legion / attribute, value)
        dmi = self.root / "class/dmi/id"
        self.write(dmi / "product_name", "82Y4")
        self.write(dmi / "bios_version", "M1CN48WW")

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(value), encoding="ascii")

    def add_nvidia(self, attached=True):
        gpu = self.pci / "0000:01:00.0"
        audio = self.pci / "0000:01:00.1"
        for path, device_class in ((gpu, "0x030000"), (audio, "0x040300")):
            self.write(path / "vendor", "0x10de")
            self.write(path / "class", device_class)
            if attached:
                (path / "driver").symlink_to("driver-name")
        self.write(gpu / "power_state", "D3cold")
        self.write(gpu / "power/runtime_status", "suspended")
        self.write(gpu / "power/runtime_usage", "0")
        return gpu, audio

    def test_firmware_modes_and_pci_state_are_separate(self):
        self.add_nvidia()
        self.assertEqual(self.graphics.choices(), list(Mode))
        status = self.graphics.status()
        self.assertEqual(status["selected_mode"], "hybrid-igpu-only")
        self.assertEqual(status["dgpu_state"], "attached")
        self.assertEqual(status["available_modes"], [mode.value for mode in Mode])

    def test_desktop_request_disconnects_at_next_boot(self):
        self.write(self.legion / "igpumode", 0)
        gpu, audio = self.add_nvidia()
        self.write(gpu / "power_state", "D0")
        command = ["legion_cli", "graphics-mode", "set", "hybrid-igpu-only"]
        with (
            patch("sys.argv", command),
            patch.object(legion_cli, "GraphicsMode", return_value=self.graphics),
            patch.object(self.graphics, "_boot_id", return_value="desktop-boot"),
            patch.object(self.graphics, "_write") as write,
            patch.object(self.graphics, "_check_clients") as check_clients,
            redirect_stdout(StringIO()) as output,
        ):
            self.assertEqual(legion_cli.main(), 0)
            self.assertIn("Restart to disconnect NVIDIA", output.getvalue())
            self.assertEqual(self.graphics.status()["pending_mode"], "hybrid-igpu-only")
            self.assertEqual(self.graphics.selected(), Mode.HYBRID)
            self.graphics.apply()
        write.assert_not_called()
        check_clients.assert_not_called()

        self.write(gpu / "power_state", "D3cold")
        actual_write = self.graphics._write

        def firmware_write(attribute, value):
            actual_write(attribute, value)
            os.rename(gpu, self.root / "removed-gpu")
            os.rename(audio, self.root / "removed-audio")

        with (
            patch.object(self.graphics, "_boot_id", return_value="next-boot"),
            patch("legion_linux.graphics.time.sleep"),
            patch.object(self.graphics, "_check_clients"),
            patch.object(self.graphics, "_write", side_effect=firmware_write) as write,
        ):
            self.graphics.apply()
        write.assert_called_once_with("igpumode", 1)
        status = self.graphics.status()
        self.assertEqual(status["selected_mode"], "hybrid-igpu-only")
        self.assertEqual(status["dgpu_state"], "detached")
        self.assertIsNone(status["pending_mode"])

    def test_removing_last_boot_installation_clears_the_request(self):
        vendor_link = self.vendor_units / "display-manager.service.wants" / UNIT_NAME
        self.write(self.vendor_units / UNIT_NAME, "[Unit]\n")
        vendor_link.parent.mkdir()
        vendor_link.symlink_to(Path("..", UNIT_NAME))
        boot = self.graphics.boot
        with (
            patch.object(boot, "_check_local_paths"),
            patch.object(boot, "status", return_value={"setup_unavailable": None}),
            patch.object(boot, "reload"),
        ):
            self.graphics.configure_boot_support(BootSupportAction.ENABLE)
            self.assertTrue(boot.unit.is_file())
            self.assertTrue(boot.link.is_symlink())
            self.graphics.set(Mode.IGPU_ONLY)
            self.graphics.configure_boot_support(BootSupportAction.DISABLE)
            self.assertFalse(boot.unit.exists())
            self.assertFalse(boot.link.is_symlink())
            self.assertTrue(vendor_link.is_file())
            self.assertTrue(self.graphics.pending.is_file())
            vendor_link.unlink()
            self.graphics.configure_boot_support(BootSupportAction.CLEANUP)
            self.assertFalse(self.graphics.pending.exists())
        self.assertEqual(self.graphics.selected(), Mode.IGPU_ONLY)

    def test_package_cleanup_preserves_appimage_switch(self):
        boot = self.graphics.boot
        with (
            patch.object(boot, "_check_local_paths"),
            patch.object(boot, "status", return_value={"setup_unavailable": None}),
            patch.object(boot, "reload"),
        ):
            self.graphics.configure_boot_support(BootSupportAction.ENABLE)
            self.graphics.set(Mode.IGPU_ONLY)
            self.graphics.configure_boot_support(BootSupportAction.CLEANUP)
        self.assertTrue(boot.link.is_file())
        self.assertTrue(self.graphics.pending.is_file())

    def test_failed_startup_keeps_request_until_it_is_canceled(self):
        self.write(self.legion / "igpumode", 0)
        self.add_nvidia()
        with patch.object(self.graphics, "_boot_id", return_value="desktop-boot"):
            self.graphics.set(Mode.IGPU_ONLY)
        with (
            patch.object(self.graphics, "_boot_id", return_value="next-boot"),
            patch.object(self.graphics, "_check_clients", side_effect=RuntimeError("Processes are using NVIDIA.")),
            patch.object(self.graphics, "_write") as write,
        ):
            with self.assertRaisesRegex(RuntimeError, "Processes are using NVIDIA"):
                self.graphics.apply()
            self.assertEqual(self.graphics.status()["pending_mode"], "hybrid-igpu-only")
            self.graphics.set(Mode.HYBRID)
            self.assertIsNone(self.graphics.status()["pending_mode"])
        write.assert_not_called()

    def test_unprivileged_user_cannot_queue_switch(self):
        with (
            patch("legion_linux.graphics.os.geteuid", return_value=1000),
            self.assertRaisesRegex(RuntimeError, "as root"),
        ):
            self.graphics.set(Mode.IGPU_ONLY)
        self.assertIsNone(self.graphics.status()["pending_mode"])

    def test_apply_retries_presence_notification(self):
        gpu, audio = self.add_nvidia()
        writes = []

        def firmware_write(attribute, value):
            writes.append((attribute, value))
            if len(writes) == 2:
                os.rename(gpu, self.root / "removed-gpu")
                os.rename(audio, self.root / "removed-audio")

        with (
            patch("legion_linux.graphics.time.sleep"),
            patch.object(self.graphics, "_check_clients"),
            patch.object(self.graphics, "_write", side_effect=firmware_write),
        ):
            self.graphics.apply()
        self.assertEqual(writes, [("notify_dgpu", 1), ("notify_dgpu", 1)])
        self.assertEqual(self.graphics.status()["dgpu_state"], "detached")

    def test_busy_gpu_leaves_firmware_alone(self):
        self.add_nvidia()
        with (
            patch.object(self.graphics, "_check_clients", side_effect=RuntimeError("Processes are using NVIDIA.")),
            patch.object(self.graphics, "_write") as write,
        ):
            with self.assertRaisesRegex(RuntimeError, "Processes are using NVIDIA"):
                self.graphics.apply()
        write.assert_not_called()

    def test_empty_lsof_result_and_inspection_failure(self):
        gpu, audio = self.add_nvidia()
        self.write(self.root / "dev/nvidia0", "")
        self.graphics.devices = self.root / "dev"
        with (
            patch.object(Path, "is_char_device", return_value=True),
            patch("legion_linux.graphics.subprocess.run") as run,
        ):
            run.return_value = CompletedProcess([], 1, "", "")
            self.graphics._check_clients(gpu, audio)
            run.return_value = CompletedProcess([], 1, "", "Permission denied")
            with self.assertRaisesRegex(RuntimeError, "Permission denied"):
                self.graphics._check_clients(gpu, audio)

    def test_no_retry_after_a_partial_removal(self):
        _, audio = self.add_nvidia()

        def firmware_write(*_):
            os.rename(audio, self.root / "removed-audio")

        with (
            patch("legion_linux.graphics.time.sleep"),
            patch.object(self.graphics, "_check_clients"),
            patch.object(self.graphics, "_write", side_effect=firmware_write) as write,
        ):
            with self.assertRaisesRegex(RuntimeError, "incomplete switch"):
                self.graphics.apply()
        write.assert_called_once_with("notify_dgpu", 1)

    def test_unverified_model_cannot_request_disconnection(self):
        self.add_nvidia()
        self.write(self.root / "class/dmi/id/product_name", "other")
        with self.assertRaisesRegex(RuntimeError, "verified on the Legion Slim 7"):
            self.graphics.apply()

    def test_hybrid_skips_the_startup_disconnect(self):
        self.write(self.legion / "igpumode", 0)
        with patch.object(self.graphics, "_write") as write:
            self.graphics.apply()
        write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
