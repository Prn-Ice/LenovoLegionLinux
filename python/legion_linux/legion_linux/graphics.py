"""Read Lenovo graphics modes and apply iGPU-only before sign-in."""

from enum import Enum
import os
from pathlib import Path
import subprocess
import time

from legion_linux.legion import LEGION_SYS_BASEPATH


class Mode(str, Enum):
    HYBRID = "hybrid"
    IGPU_ONLY = "hybrid-igpu-only"
    AUTO = "hybrid-auto"
    DISCRETE = "discrete"


IGPU_MODES = (Mode.HYBRID, Mode.IGPU_ONLY, Mode.AUTO)


class GraphicsMode:
    def __init__(self, legion=Path(LEGION_SYS_BASEPATH), sysfs=Path("/sys"), devices=Path("/dev")):
        self.legion = legion
        self.sysfs = sysfs
        self.devices = devices

    def _read(self, attribute):
        return (self.legion / attribute).read_text(encoding="ascii").strip()

    def _write(self, attribute, value):
        path = self.legion / attribute
        path.write_text(f"{value}\n", encoding="ascii")
        if attribute != "notify_dgpu" and self._read(attribute) != str(value):
            raise RuntimeError(f"Firmware did not accept {attribute}={value}.")

    def _supports(self, attribute):
        try:
            return int(self._read(f"issupport{attribute}")) > 0 and (self.legion / attribute).is_file()
        except FileNotFoundError:
            return False

    def choices(self):
        mux = self._supports("gsync")
        policy = self._supports("igpumode")
        modes = list(IGPU_MODES if policy else [Mode.HYBRID] if mux else [])
        if mux:
            modes.append(Mode.DISCRETE)
        return modes

    def selected(self):
        modes = self.choices()
        if not modes:
            raise RuntimeError("The firmware does not expose graphics modes.")
        if Mode.DISCRETE in modes and self._read("gsync") == "0":
            return Mode.DISCRETE
        if Mode.IGPU_ONLY not in modes:
            return Mode.HYBRID
        raw = int(self._read("igpumode"))
        if not 0 <= raw < len(IGPU_MODES):
            raise RuntimeError(f"Unknown firmware iGPU mode {raw}.")
        return IGPU_MODES[raw]

    def _nvidia_functions(self):
        devices = self.sysfs / "bus/pci/devices"
        functions = []
        for entry in devices.iterdir():
            try:
                vendor = (entry / "vendor").read_text(encoding="ascii").strip()
            except FileNotFoundError:
                continue
            if vendor == "0x10de":
                functions.append(entry)
        return functions

    def status(self):
        functions = self._nvidia_functions()
        state = "detached"
        if functions:
            display = any((device / "class").read_text(encoding="ascii").startswith("0x03") for device in functions)
            state = (
                "attached" if display and all((device / "driver").is_symlink() for device in functions) else "partial"
            )
        return {"selected_mode": self.selected().value, "dgpu_state": state}

    def _check_model(self):
        dmi = self.sysfs / "class/dmi/id"
        model = (dmi / "product_name").read_text(encoding="ascii").strip()
        bios = (dmi / "bios_version").read_text(encoding="ascii").strip()
        if model != "82Y4" or not bios.startswith("M1CN"):
            raise RuntimeError("iGPU-only disconnection has been verified on the Legion Slim 7 16APH8 (82Y4).")

    @staticmethod
    def _check_attached(functions):
        graphics = [device for device in functions if (device / "class").read_text(encoding="ascii").startswith("0x03")]
        audio = [device for device in functions if (device / "class").read_text(encoding="ascii").startswith("0x04")]
        if (
            len(functions) != 2
            or len(graphics) != 1
            or len(audio) != 1
            or graphics[0].name[:-1] != audio[0].name[:-1]
            or not all((device / "driver").is_symlink() for device in functions)
        ):
            raise RuntimeError(
                "NVIDIA graphics and audio must both be attached. Restart to recover an incomplete switch."
            )
        return graphics[0], audio[0]

    @staticmethod
    def _asleep(gpu):
        return all(
            (gpu / attribute).read_text(encoding="ascii").strip() == expected
            for attribute, expected in (
                ("power_state", "D3cold"),
                ("power/runtime_status", "suspended"),
                ("power/runtime_usage", "0"),
            )
        )

    def _check_clients(self, gpu, audio):
        drm = [self.devices / "dri" / node.name for node in (gpu / "drm").glob("*") if "-" not in node.name]
        sound = [
            self.devices / "snd" / node.name
            for node in (self.sysfs / "class/sound").glob("*")
            if audio.resolve() in node.resolve().parents
        ]
        nvidia = [*self.devices.glob("nvidia*"), *(self.devices / "nvidia-caps").glob("*")]
        nodes = sorted({node for node in [*nvidia, *drm, *sound] if node.is_char_device()})
        if not nodes:
            raise RuntimeError("Could not find NVIDIA device files to check.")
        try:
            result = subprocess.run(
                ["lsof", "-nP", "-Q", "-f", "--", *map(str, nodes)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise RuntimeError("Could not inspect NVIDIA clients. Install lsof and run before sign-in.") from error
        if result.returncode != 0:
            raise RuntimeError(f"Could not inspect NVIDIA clients. {result.stderr.strip()}")
        if result.stdout.strip():
            raise RuntimeError("Processes are using NVIDIA. Run the disconnect before the sign-in screen starts.")

    def _wait_for_idle(self):
        for _ in range(30):
            functions = self._nvidia_functions()
            if not functions:
                return functions
            if all((device / "driver").is_symlink() for device in functions):
                gpu, _ = self._check_attached(functions)
                if self._asleep(gpu):
                    return functions
            time.sleep(1)
        return self._nvidia_functions()

    def _detach(self, select):
        self._check_model()
        if os.geteuid() != 0:
            raise RuntimeError("Run the iGPU-only disconnect as root before sign-in.")
        for attempt in range(5):
            functions = self._wait_for_idle() if attempt == 0 else self._nvidia_functions()
            if not functions:
                if select:
                    raise RuntimeError("NVIDIA must be present to select iGPU-only from hybrid mode.")
                return
            gpu, audio = self._check_attached(functions)
            if not self._asleep(gpu):
                raise RuntimeError("NVIDIA must be in D3cold before requesting disconnection.")
            self._check_clients(gpu, audio)
            if not self._asleep(gpu) or self.selected() != (Mode.HYBRID if select else Mode.IGPU_ONLY):
                raise RuntimeError("Graphics state changed during the device check. Try again before sign-in.")
            if select:
                self._write("igpumode", 1)
                select = False
            else:
                self._write("notify_dgpu", 1)
            time.sleep(5)
        if self._nvidia_functions():
            raise RuntimeError("The firmware request did not disconnect NVIDIA.")

    def apply(self):
        if self.selected() == Mode.IGPU_ONLY:
            self._detach(select=False)
            return "NVIDIA graphics and audio are disconnected."
        return "The selected graphics mode does not need a startup disconnect."

    def set(self, mode):
        selected = self.selected()
        if mode not in self.choices():
            raise RuntimeError(f"The firmware does not advertise {mode.value}.")
        if mode == Mode.AUTO:
            raise RuntimeError("Hybrid Auto can eject NVIDIA after an AC power change. Automatic switching is pending.")
        if mode == Mode.IGPU_ONLY:
            if selected not in (Mode.HYBRID, Mode.IGPU_ONLY):
                raise RuntimeError("Select hybrid and restart before switching to iGPU-only.")
            self._detach(select=selected == Mode.HYBRID)
            return "iGPU-only is active. NVIDIA graphics and audio are disconnected."
        if mode == selected:
            return f"{mode.value} is already selected."
        if selected in (Mode.IGPU_ONLY, Mode.AUTO):
            self._check_model()
            functions = self._nvidia_functions()
            if functions:
                self._check_attached(functions)
            self._write("igpumode", 0)
        if Mode.DISCRETE in (mode, selected):
            # The firmware reports the current MUX position until the next boot.
            (self.legion / "gsync").write_text(f"{int(mode == Mode.HYBRID)}\n", encoding="ascii")
            return f"Requested {mode.value}. Restart to apply the display routing."
        return "Hybrid is selected."
