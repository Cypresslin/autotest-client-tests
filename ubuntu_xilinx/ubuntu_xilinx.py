from autotest.client import test, utils
import os

class ubuntu_xilinx(test.test):
    version = 1

    def initialize(self):
        pass

    def setup(self):
        snap_pkgs = ['xlnx-config']
        cmd = 'snap install --classic ' + ' '.join(snap_pkgs)
        utils.system_output(cmd, retain_output=True)

    def run_once(self, test_name):
        cmd = os.path.join(self.bindir, 'tests', test_name)
        utils.system_output(cmd, retain_output=True)

# vi:set ts=4 sw=4 expandtab syntax=python:
