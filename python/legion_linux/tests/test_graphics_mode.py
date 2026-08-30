import os
import tempfile
import unittest
from unittest.mock import patch

from legion_linux import legion


class GraphicsModeFeatureTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.files = {
            'gsync': '1',
            'issupportgsync': '2',
            'igpumode': '0',
            'issupportigpumode': '3',
        }
        for name, value in self.files.items():
            with open(os.path.join(self.temp_dir.name, name), 'w',
                      encoding=legion.DEFAULT_ENCODING) as filepointer:
                filepointer.write(value)

        self.path_patch = patch.object(
            legion, 'LEGION_SYS_BASEPATH', self.temp_dir.name)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.feature = legion.GraphicsModeFeature(legion.GsyncFeature())

    def read(self, name):
        with open(os.path.join(self.temp_dir.name, name), 'r',
                  encoding=legion.DEFAULT_ENCODING) as filepointer:
            return filepointer.read()

    def write(self, name, value):
        with open(os.path.join(self.temp_dir.name, name), 'w',
                  encoding=legion.DEFAULT_ENCODING) as filepointer:
            filepointer.write(str(value))

    def test_reports_combined_mode_and_choices(self):
        self.assertEqual('hybrid', self.feature.get())
        self.assertEqual(
            ['hybrid', 'hybrid-igpu-only', 'hybrid-auto', 'discrete'],
            self.feature.choices())

        self.write('igpumode', 1)
        self.assertEqual('hybrid-igpu-only', self.feature.get())

        self.write('igpumode', 2)
        self.assertEqual('hybrid-auto', self.feature.get())

        self.write('gsync', 0)
        self.assertEqual('discrete', self.feature.get())

    def test_applies_safe_transition_order_and_readback(self):
        self.feature.set('hybrid-igpu-only')
        self.assertEqual('1', self.read('gsync'))
        self.assertEqual('1', self.read('igpumode'))

        self.feature.set('discrete')
        self.assertEqual('0', self.read('gsync'))
        self.assertEqual('0', self.read('igpumode'))

    def test_rolls_back_first_write_when_second_write_fails(self):
        self.write('gsync', 0)

        def fail_igpu_write(_):
            raise IOError('injected failure')

        self.feature.igpu_mode.set = fail_igpu_write

        with self.assertRaisesRegex(IOError, 'injected failure'):
            self.feature.set('hybrid-igpu-only')

        self.assertEqual('0', self.read('gsync'))
        self.assertEqual('0', self.read('igpumode'))

    def test_reports_rollback_readback_failure(self):
        self.write('gsync', 0)
        write_gsync = self.feature.gsync.set

        def ignore_gsync_rollback(value):
            if value:
                write_gsync(value)

        def fail_igpu_write(_):
            raise IOError('injected failure')

        self.feature.gsync.set = ignore_gsync_rollback
        self.feature.igpu_mode.set = fail_igpu_write

        with self.assertRaisesRegex(IOError, 'rollback also failed'):
            self.feature.set('hybrid-igpu-only')

        self.assertEqual('1', self.read('gsync'))

    def test_rejects_unknown_firmware_mode(self):
        self.write('igpumode', 9)
        with self.assertRaisesRegex(ValueError, 'invalid iGPU mode 9'):
            self.feature.get()


if __name__ == '__main__':
    unittest.main()
