"""Set up the one-shot graphics command in systemd's local unit directory."""

from enum import Enum
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile

UNIT_NAME = "legion-graphics.service"
BOOT_PATH = "/run/current-system/sw/bin:/usr/local/bin:/usr/bin:/bin"
LOCAL_UNITS = Path("/etc/systemd/system.attached")
SYSTEM_UNITS = (
    Path("/etc/systemd/system"),
    Path("/usr/local/lib/systemd/system"),
    Path("/usr/lib/systemd/system"),
    Path("/lib/systemd/system"),
)
OWNER = "# Installed by legion_cli for AppImage graphics boot support.\n"


class BootSupportAction(str, Enum):
    ENABLE = "enable"
    DISABLE = "disable"
    CLEANUP = "cleanup"


def _wants_directory(unit_directory):
    return unit_directory / "display-manager.service.wants"


def _enabled(unit_directory):
    link = _wants_directory(unit_directory) / UNIT_NAME
    return link.is_symlink() and link.is_file()


class GraphicsBoot:
    def __init__(self, local=LOCAL_UNITS, system=SYSTEM_UNITS):
        self.local = local
        self.system = system
        self.unit = local / UNIT_NAME
        self.link = _wants_directory(local) / UNIT_NAME

    def _owns_unit(self):
        if self.unit.is_symlink() or not self.unit.is_file():
            return False
        try:
            with self.unit.open(encoding="ascii", errors="replace") as stream:
                return stream.readline(len(OWNER)) == OWNER
        except FileNotFoundError:
            return False

    def enabled(self):
        return any(_enabled(location) for location in (*self.system, self.local))

    def status(self, supported_model):
        reason = None
        if not supported_model:
            reason = "unsupported-model"
        elif not Path("/run/systemd/system").is_dir():
            reason = "missing-systemd"
        elif not shutil.which("lsof", path=BOOT_PATH):
            reason = "missing-lsof"
        return {
            "enabled": supported_model and Path("/run/systemd/system").is_dir() and self.enabled(),
            "appimage_enabled": self._owns_unit() and _enabled(self.local),
            "setup_unavailable": reason,
        }

    def _check_local_paths(self):
        for directory in (*reversed(self.link.parent.parents), self.link.parent):
            if not directory.exists() and not directory.is_symlink():
                continue
            info = directory.lstat()
            if directory.is_symlink() or not directory.is_dir() or info.st_uid != 0 or info.st_mode & 0o022:
                raise RuntimeError(f"Boot support requires an administrator-controlled directory: {directory}.")
        if (self.unit.exists() or self.unit.is_symlink()) and not self._owns_unit():
            raise RuntimeError(f"Another installation owns {self.unit}.")
        if self.link.is_symlink() and self.link.readlink() == Path("..", UNIT_NAME):
            return
        if self.link.exists() or self.link.is_symlink():
            raise RuntimeError(f"Another installation owns {self.link}.")

    def configure(self, enable):
        self._check_local_paths()
        if enable:
            self.link.parent.mkdir(parents=True, exist_ok=True)
            if not self._owns_unit():
                template = Path(__file__).with_name(UNIT_NAME).read_text(encoding="ascii")
                with NamedTemporaryFile(mode="w", dir=self.local, encoding="ascii", delete=False) as stream:
                    temporary = Path(stream.name)
                    try:
                        stream.write(OWNER + template)
                        stream.flush()
                        os.fchmod(stream.fileno(), 0o644)
                        temporary.replace(self.unit)
                    finally:
                        temporary.unlink(missing_ok=True)
            if not self.link.is_symlink():
                self.link.symlink_to(Path("..", UNIT_NAME))
        else:
            if not self._owns_unit():
                return
            if self.link.is_symlink():
                self.link.unlink()
            self.unit.unlink()

    @staticmethod
    def reload():
        systemctl = shutil.which("systemctl", path=BOOT_PATH)
        if systemctl and Path("/run/systemd/system").is_dir():
            subprocess.run([systemctl, "daemon-reload"], check=True, timeout=5)
