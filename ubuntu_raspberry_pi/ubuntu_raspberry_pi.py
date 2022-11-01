#
#
from autotest.client import test, utils
import os
import shutil

TEST_REPOSITORY = 'git://git.launchpad.net/~canonical-kernel-team/+git/raspi-rt-tests'


class ubuntu_raspberry_pi(test.test):
    version = 1

    def initialize(self):
        pass

    def setup(self, test_name):
        os.chdir(self.srcdir)
        shutil.rmtree('raspi-rt-tests', ignore_errors=True)
        cmd = 'git clone --depth=1 ' + TEST_REPOSITORY + ' raspi-rt-tests'
        utils.system(cmd)
        os.chdir(os.path.join(self.srcdir, 'raspi-rt-tests'))
        cmd = 'sudo ./install-deps'
        utils.system(cmd)

    def run_once(self, test_name):
        if test_name == 'setup':
            return

        cmd = os.path.join(self.srcdir, 'raspi-rt-tests', 'tests', test_name)
        utils.system_output(cmd, retain_output=True)

# vi:set ts=4 sw=4 expandtab syntax=python:
