#
#
from autotest.client import test, utils
import os
import shutil

TEST_REPOSITORY = 'git://git.launchpad.net/~canonical-kernel-team/+git/overlay-shiftfs-tests'
TEST_BRANCH = 'main'
TEST_DIR = 'overlay-shiftfs-tests'


class ubuntu_overlayfs_smoke_test(test.test):
    version = 1

    def initialize(self):
        pass

    def setup(self, test_name):
        os.chdir(self.srcdir)
        shutil.rmtree('overlay-shiftfs-tests', ignore_errors=True)
        cmd = 'git clone --depth=1 -b {} {} {}'.format(TEST_BRANCH, TEST_REPOSITORY, TEST_DIR)
        utils.system(cmd)
        os.chdir(os.path.join(self.srcdir, TEST_DIR))
        cmd = 'sudo ./install-deps'
        utils.system(cmd)

    def run_once(self, test_name):
        if test_name == 'setup':
            return

        cmd = os.path.join(self.srcdir, TEST_DIR, 'tests', test_name)
        cmd = 'sudo -iu {} {}'.format(os.getlogin(), cmd)
        self.results = utils.system_output(cmd, retain_output=True)
        print(self.results)

# vi:set ts=4 sw=4 expandtab syntax=python:
