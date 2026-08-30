#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# pylint: disable=wrong-import-order
import argcomplete
import argparse
import logging
import sys
import os
import subprocess
# Make it possible to run without installationimport
# pylint: disable=# pylint: disable=wrong-import-position
sys.path.insert(0, os.path.dirname(__file__) + "/..")
import legion_linux.legion
from legion_linux.legion import LegionModelFacade
logging.basicConfig()
log = logging.getLogger(legion_linux.legion.__name__)
loglevels = ['NOTSET', 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
# will be set in main to user defined level after parsing
log.setLevel('ERROR')


class CLIFeatureCommand:
    def __init__(self, name: str, parser_subcommands, cmd_group: list, writeable: bool = True):
        self.name = name
        self.model = None
        status_parser = parser_subcommands.add_parser(
            f"{self.name}-status", help=f'Get current value for {self.name}')
        status_parser.set_defaults(
            func=lambda l, *args, **kwargs: self.command_status_cli(**kwargs))

        if writeable:
            enable_parser = parser_subcommands.add_parser(
                f"{self.name}-enable", help=f'Enable {self.name}')
            enable_parser.set_defaults(
                func=lambda l, *args, **kwargs: self.command_enable_cli(**kwargs))

            disable_parser = parser_subcommands.add_parser(
                f"{self.name}-disable", help=f'Disable {self.name}')
            disable_parser.set_defaults(
                func=lambda l, *args, **kwargs: self.command_disable_cli(**kwargs))

        if cmd_group is not None:
            cmd_group.append(self)

    def set_model(self, model: LegionModelFacade):
        self.model = model

    def check_if_exist(self):
        if self.exists():
            return True
        print(
            "Command not available because feature is not available or kernel module is not loaded.")
        return False

    def command_status_cli(self, **_) -> int:
        if self.check_if_exist():
            return self.command_status()
        return -10

    def command_enable_cli(self, **_) -> int:
        if self.check_if_exist():
            return self.command_enable()
        return -10

    def command_disable_cli(self, **_) -> int:
        if self.check_if_exist():
            return self.command_disable()
        return -10

    def exists(self) -> bool:
        return False

    def command_status(self, **_) -> int:
        return 0

    def command_enable(self, **_) -> int:
        return -1

    def command_disable(self, **_) -> int:
        return -1


class MiniFancurveFeatureCommand(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("minifancurve", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.fancurve_io.exists()

    def command_status(self, **_) -> int:
        print(self.model.fancurve_io.get_minifancuve())
        return 0

    def command_enable(self, **_) -> int:
        self.model.fancurve_io.set_minifancuve(True)
        return 0

    def command_disable(self, **_) -> int:
        self.model.fancurve_io.set_minifancuve(False)
        return 0


class LockFanControllerFeatureCommand(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("lockfancontroller", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.lockfancontroller.exists()

    def command_status(self, **_) -> int:
        print(self.model.lockfancontroller.get())
        return 0

    def command_enable(self, **_) -> int:
        self.model.lockfancontroller.set(True)
        return 0

    def command_disable(self, **_) -> int:
        self.model.lockfancontroller.set(False)
        return 0


class MaximumFanSpeedFeatureCommand(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("maximumfanspeed", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.maximum_fanspeed.exists()

    def command_status(self, **_) -> int:
        print(self.model.maximum_fanspeed.get())
        return 0

    def command_enable(self, **_) -> int:
        self.model.maximum_fanspeed.set(True)
        return 0

    def command_disable(self, **_) -> int:
        self.model.maximum_fanspeed.set(False)
        return 0


class BatteryConservationFeatureCommand(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("batteryconservation", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.battery_conservation.exists()

    def command_status(self, **_) -> int:
        print(self.model.battery_conservation.get())
        return 0

    def command_enable(self, **_) -> int:
        self.model.battery_conservation.set(True)
        return 0

    def command_disable(self, **_) -> int:
        self.model.battery_conservation.set(False)
        return 0


class FnLockFeatureCommand(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("fnlock", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.fn_lock.exists()

    def command_status(self, **_) -> int:
        print(self.model.fn_lock.get())
        return 0

    def command_enable(self, **_) -> int:
        self.model.fn_lock.set(True)
        return 0

    def command_disable(self, **_) -> int:
        self.model.fn_lock.set(False)
        return 0


class TouchpadFeatureCommand(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("touchpad", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.touchpad.exists()

    def command_status(self, **_) -> int:
        print(self.model.touchpad.get())
        return 0

    def command_enable(self, **_) -> int:
        self.model.touchpad.set(True)
        return 0

    def command_disable(self, **_) -> int:
        self.model.touchpad.set(False)
        return 0


class CameraPowerFeatureCommand(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("camera-power", parser_subcommands, cmd_group, False)
        self.model = model

    def exists(self) -> bool:
        return self.model.camera_power.exists()

    def command_status(self, **_) -> int:
        print(self.model.camera_power.get())
        return 0


class OnPowerSupplyFeatureCommand(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("on-power-supply", parser_subcommands, cmd_group, False)
        self.model = model

    def exists(self) -> bool:
        return self.model.on_power_supply.exists()

    def command_status(self, **_) -> int:
        print(self.model.on_power_supply.get())
        return 0


class AlwaysOnUsbCharging(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("always-on-usb-charging", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.always_on_usb_charging.exists()

    def command_status(self, **_) -> int:
        print(self.model.always_on_usb_charging.get())
        return 0

    def command_enable(self, **_) -> int:
        self.model.always_on_usb_charging.set(True)
        return 0

    def command_disable(self, **_) -> int:
        self.model.always_on_usb_charging.set(False)
        return 0


class RapidCharging(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("rapid-charging", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.rapid_charging.exists()

    def command_status(self, **_) -> int:
        print(self.model.rapid_charging.get())
        return 0

    def command_enable(self, **_) -> int:
        self.model.rapid_charging.set(True)
        return 0

    def command_disable(self, **_) -> int:
        self.model.rapid_charging.set(False)
        return 0


class HybridMode(CLIFeatureCommand):
    def __init__(self, parser_subcommands, model: LegionModelFacade, cmd_group: list):
        super().__init__("hybrid-mode", parser_subcommands, cmd_group)
        self.model = model

    def exists(self) -> bool:
        return self.model.gsync.exists()

    def command_status(self, **_) -> int:
        print("This is the current state. Changing it by setting it will apply only after a reboot.")
        print(self.model.gsync.get())
        return 0

    def command_enable(self, **_) -> int:
        print("Changes will only apply after a reboot.")
        self.model.gsync.set(True)
        return 0

    def command_disable(self, **_) -> int:
        print("Changes will only apply after a reboot.")
        self.model.gsync.set(False)
        return 0


def autocomplete_install(_, **__) -> int:
    cmd = f"eval \"$(register-python-argcomplete {__file__})\""
    print("PLEASE RUN THE COMMAND:")
    print(cmd)


def fancurve_write_preset_to_hw(legion: LegionModelFacade, presetname: str, **_) -> int:
    # pylint: disable=unused-argument
    legion.fancurve_write_preset_to_hw(presetname, write_minifancurve=True)
    print(f'Successfully wrote preset {presetname} to hardware')
    return 0


def fancurve_write_hw_to_preset(legion: LegionModelFacade, presetname: str, **_) -> int:
    # pylint: disable=unused-argument
    legion.fancurve_write_hw_to_preset(presetname)
    print(f'Successfully wrote hardware to preset {presetname}')
    return 0


def fancurve_write_file_to_hw(legion: LegionModelFacade, filename: str, **_) -> int:
    # pylint: disable=unused-argument
    legion.fancurve_write_file_to_hw(filename, write_minifancurve=True)
    print(f'Successfully wrote fan curve from file {filename} to hardware')
    return 0


def fancurve_write_hw_to_file(legion: LegionModelFacade, filename: str, **_) -> int:
    # pylint: disable=unused-argument
    legion.fancurve_write_hw_to_file(filename)
    print(f'Successfully wrote fan curve from hardware to file {filename}')
    return 0


def fancurve_write_preset_for_current_profile(legion: LegionModelFacade, **_) -> int:
    # pylint: disable=unused-argument
    legion.fancurve_write_preset_for_current_profile(write_minifancurve=True)
    return 0


def conservation_apply_mode_for_current_battery_capacity(legion: LegionModelFacade,
                                                         lowerlimit=50, upperlimit=60, **_) -> int:
    print(legion.conservation_apply_mode_for_current_battery_capacity(
        lowerlimit, upperlimit))
    return 0


def monitor(legion: LegionModelFacade, period=None, **_) -> int:
    print("Starting monitoring:")
    legion.run_monitors(period_s=period)
    return 0


def set_feature(legion: LegionModelFacade, name, values, **_) -> int:
    log.setLevel('INFO')
    if legion.set_feature_to_str_value(name, values):
        return 0
    print("Feature not found.")
    for feat in legion.get_all_features():
        print(feat)
    return -2


def graphics_mode_status(legion: LegionModelFacade, **_) -> int:
    try:
        if not legion.graphics_mode.exists():
            print('Graphics mode is not supported.')
            return 1
        print(legion.graphics_mode.get())
    except (IOError, ValueError) as error:
        print(f'Failed to read graphics mode: {error}')
        return 1
    return 0


def graphics_mode_choices(legion: LegionModelFacade, **_) -> int:
    try:
        choices = legion.graphics_mode.choices()
    except (IOError, ValueError) as error:
        print(f'Failed to read graphics mode choices: {error}')
        return 1
    if not choices:
        print('Graphics mode is not supported.')
        return 1
    print('\n'.join(choices))
    return 0


def graphics_mode_set(legion: LegionModelFacade, mode: str, **_) -> int:
    try:
        legion.graphics_mode.set(mode)
    except (FileNotFoundError, IOError, ValueError) as error:
        print(error)
        return 1

    if mode == legion.graphics_mode.DISCRETE:
        print('Graphics mode set to discrete. Reboot is required.')
    elif mode in (legion.graphics_mode.HYBRID_IGPU_ONLY,
                  legion.graphics_mode.HYBRID_AUTO):
        print(f'Graphics mode set to {mode}. Live dGPU availability may change.')
    else:
        print('Graphics mode set to hybrid. A MUX change may require reboot.')
    return 0

def create_argparser()->argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Legion CLI')
    parser.add_argument(
        '--donotexpecthwmon', action='store_true', help='Do not check hwmon dir when not needed', default=False)
    parser.add_argument('--loglevel', type=str,
                        help='Level of log output', choices=loglevels, default='ERROR')

    subcommands = parser.add_subparsers(title='subcommands', dest='subcommand')

    autocomplete_install_parser = subcommands.add_parser(
        'autocomplete-install', help='Install autocompletion in shell for this tool')
    autocomplete_install_parser.set_defaults(func=autocomplete_install)

    preset_to_hw_parser = subcommands.add_parser(
        'fancurve-write-preset-to-hw', help='Write fan curve from preset to hardware')
    preset_to_hw_parser.add_argument(
        'presetname', type=str, help='Name of the preset')
    preset_to_hw_parser.add_argument(
        '--preset-dir', type=str, help='Path of the directory with presets')
    preset_to_hw_parser.set_defaults(func=fancurve_write_preset_to_hw)

    hw_to_preset_parser = subcommands.add_parser(
        'fancurve-write-hw-to-preset', help='Write fan curve from hardware to preset')
    hw_to_preset_parser.add_argument(
        'presetname', type=str, help='Name of the preset')
    hw_to_preset_parser.add_argument(
        '--preset-dir', type=str, help='Path of the directory with presets')
    hw_to_preset_parser.set_defaults(func=fancurve_write_hw_to_preset)

    file_to_hw_parser = subcommands.add_parser(
        'fancurve-write-file-to-hw', help='Write fan curve from file to hardware')
    file_to_hw_parser.add_argument(
        'filename', type=str, help='Name of the file')
    file_to_hw_parser.set_defaults(func=fancurve_write_file_to_hw)

    hw_to_file_parser = subcommands.add_parser(
        'fancurve-write-hw-to-file', help='Write fan curve from hardware to file')
    hw_to_file_parser.add_argument(
        'filename', type=str, help='Name of the file')
    hw_to_file_parser.set_defaults(func=fancurve_write_hw_to_file)

    hw_to_file_parser = subcommands.add_parser(
        'fancurve-write-current-preset-to-hw',
        help='Write fan curve for the current profile (power mode, power supply status) to hardware')
    hw_to_file_parser.set_defaults(
        func=fancurve_write_preset_for_current_profile)

    custom_conservation_mode = subcommands.add_parser(
        'custom-conservation-mode-apply', help='Turn conservation mode on or off depending on battery level')
    custom_conservation_mode.add_argument(
        'lowerlimit', type=int, help='Limit when conservation mode should be turned off, e.g. 60', default=61)
    custom_conservation_mode.add_argument(
        'upperlimit', type=int, help='Limit when conservation mode should be turned on, e.g. 80', default=81)
    custom_conservation_mode.set_defaults(
        func=conservation_apply_mode_for_current_battery_capacity)

    monitor_cmd = subcommands.add_parser(
        'monitor', help='Run monitors with notifications')
    monitor_cmd.add_argument(
        'period', type=int, help='Monitoring period in seconds', default=60)
    monitor_cmd.set_defaults(
        func=monitor)

    set_feature_cmd = subcommands.add_parser(
        'set-feature', help='Set feature')
    set_feature_cmd.add_argument(
        'name', type=str, help='Name of feature')
    set_feature_cmd.add_argument(
        'values', type=str, help='Value of feature', nargs='+')
    set_feature_cmd.set_defaults(
        func=set_feature)

    bootlogo_parser = subcommands.add_parser('boot-logo', help="Custom Boot Logo")
    bootlogo_sub = bootlogo_parser.add_subparsers(dest='bootlogo_cmd')
    enable_parser = bootlogo_sub.add_parser('enable', help='Set Boot Logo')
    enable_parser.add_argument('image_path', type=str, help='Path to the image to be used')
    enable_parser.set_defaults(func=lambda legion, **kw: boot_logo_enable(legion, **kw))
    restore_parser = bootlogo_sub.add_parser('restore', help='Restore modified boot logo')
    restore_parser.set_defaults(func=lambda legion, **kw: boot_logo_restore(legion, **kw))
    status_parser = bootlogo_sub.add_parser('status', help='View status')
    status_parser.set_defaults(func=lambda legion, **kw: boot_logo_status(legion, **kw))

    dgpu_parser = subcommands.add_parser('dgpu', help='Discrete GPU management')
    dgpu_sub = dgpu_parser.add_subparsers(dest='dgpu_cmd')
    dgpu_kill_parser = dgpu_sub.add_parser('kill-processes', help='Kill compute processes using the GPU')
    dgpu_kill_parser.set_defaults(func=lambda legion, **kw: dgpu_kill_processes(**kw))
    dgpu_restart_parser = dgpu_sub.add_parser('restart-pci', help='Remove and rescan GPU PCI device')
    dgpu_restart_parser.set_defaults(func=lambda legion, **kw: dgpu_restart_pci(**kw))

    graphics_mode_parser = subcommands.add_parser(
        'graphics-mode', help='Read or set the combined GPU working mode')
    graphics_mode_sub = graphics_mode_parser.add_subparsers(
        dest='graphics_mode_cmd', required=True)
    graphics_mode_status_parser = graphics_mode_sub.add_parser(
        'status', help='Print the authoritative current graphics mode')
    graphics_mode_status_parser.set_defaults(func=graphics_mode_status)
    graphics_mode_choices_parser = graphics_mode_sub.add_parser(
        'choices', help='Print the graphics modes supported by firmware')
    graphics_mode_choices_parser.set_defaults(func=graphics_mode_choices)
    graphics_mode_set_parser = graphics_mode_sub.add_parser(
        'set', help='Set a supported graphics mode')
    graphics_mode_set_parser.add_argument(
        'mode', choices=['hybrid', 'hybrid-igpu-only', 'hybrid-auto', 'discrete'])
    graphics_mode_set_parser.set_defaults(func=graphics_mode_set)

    return parser, subcommands

def boot_logo_enable(legion: LegionModelFacade, image_path: str, **kwargs) -> int:
    try:
        legion.enable_boot_logo(image_path)
        print("Boot Logo enabled.")
        return 0
    except Exception as e:
        print(f"Error enabling Boot Logo: {e}")
        return 1

def boot_logo_restore(legion: LegionModelFacade, **kwargs) -> int:
    try:
        legion.restore_boot_logo()
        print("Boot Logo restored.")
        return 0
    except Exception as e:
        print(f"Error restoring boot logo: {e}")
        return 1

def boot_logo_status(legion: LegionModelFacade, **kwargs) -> int:
    is_on, w, h = legion.get_boot_logo_status()
    print(f"Current Boot Logo status: {'ON' if is_on else 'OFF'}; Required image dimensions: {w} x {h}")
    return 0


def _find_nvidia_pci_address():
    """Return the PCI address string of the NVIDIA discrete GPU, or None."""
    import glob
    for vendor_path in glob.glob('/sys/bus/pci/devices/*/vendor'):
        try:
            with open(vendor_path) as f:
                if f.read().strip() != '0x10de':
                    continue
            class_path = vendor_path.replace('vendor', 'class')
            with open(class_path) as f:
                device_class = int(f.read().strip(), 16)
            if (device_class >> 16) == 0x03:  # Display controller
                return vendor_path.split('/')[-2]
        except (IOError, ValueError):
            continue
    return None


def dgpu_kill_processes(**kwargs) -> int:
    """Kill all compute processes using the NVIDIA GPU (requires root)."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"nvidia-smi failed: {result.stderr.strip()}")
            return 1
        pids = [line.strip() for line in result.stdout.strip().splitlines() if line.strip().isdigit()]
        if not pids:
            print("No compute processes found on GPU.")
            return 0
        import signal
        for pid_str in pids:
            try:
                os.kill(int(pid_str), signal.SIGKILL)
                print(f"Killed PID {pid_str}")
            except (ProcessLookupError, PermissionError) as e:
                print(f"Could not kill PID {pid_str}: {e}")
        return 0
    except FileNotFoundError:
        print("nvidia-smi not found. Is the NVIDIA driver installed?")
        return 1
    except Exception as e:
        print(f"Error killing GPU processes: {e}")
        return 1


def dgpu_restart_pci(**kwargs) -> int:
    """Remove the NVIDIA GPU from the PCI tree and rescan to reinitialise it (requires root)."""
    addr = _find_nvidia_pci_address()
    if not addr:
        print("Could not find NVIDIA GPU PCI address.")
        return 1
    try:
        remove_path = f"/sys/bus/pci/devices/{addr}/remove"
        with open(remove_path, 'w') as f:
            f.write('1')
        print(f"Removed PCI device {addr}")
        rescan_path = "/sys/bus/pci/rescan"
        with open(rescan_path, 'w') as f:
            f.write('1')
        print("PCI bus rescanned — device should reappear.")
        return 0
    except (IOError, PermissionError) as e:
        print(f"PCI operation failed: {e}")
        return 1


def main():
    parser, subcommands = create_argparser()

    cmd_group = []
    MiniFancurveFeatureCommand(subcommands, None, cmd_group)
    LockFanControllerFeatureCommand(subcommands, None, cmd_group)
    MaximumFanSpeedFeatureCommand(subcommands, None, cmd_group)
    BatteryConservationFeatureCommand(subcommands, None, cmd_group)
    FnLockFeatureCommand(subcommands, None, cmd_group)
    TouchpadFeatureCommand(subcommands, None, cmd_group)
    CameraPowerFeatureCommand(subcommands, None, cmd_group)
    OnPowerSupplyFeatureCommand(subcommands, None, cmd_group)
    AlwaysOnUsbCharging(subcommands, None, cmd_group)
    RapidCharging(subcommands, None, cmd_group)
    HybridMode(subcommands, None, cmd_group)

    # only add autocompletion if package is installed
    argcomplete.autocomplete(parser)

    args = parser.parse_args()
    log.setLevel(args.loglevel)

    if args.subcommand is None:
        parser.print_help()
        return 0
    else:
        legion = LegionModelFacade(expect_hwmon=not args.donotexpecthwmon)
        for cmd in cmd_group:
            cmd.set_model(legion)
        # set global options
        if "preset_dir" in args and args.preset_dir is not None:
            legion.set_preset_folder(args.preset_dir)

        return args.func(legion, **vars(args))


if __name__ == '__main__':
    sys.exit(main())
