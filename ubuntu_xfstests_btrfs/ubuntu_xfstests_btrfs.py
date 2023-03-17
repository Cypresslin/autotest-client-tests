import os
import re
import glob
import logging
import platform
import shutil
from autotest.client.shared import error
from autotest.client import test, utils
from autotest.client import canonical

class ubuntu_xfstests_btrfs(test.test):

    version = 1

    PASSED_RE = re.compile(r'Passed all \d+ tests')
    FAILED_RE = re.compile(r'Failed \d+ of \d+ tests')
    NA_RE = re.compile(r'Passed all 0 tests')
    NA_DETAIL_RE = re.compile(r'(\d{3})\s*(\[not run\])\s*(.*)')
    GROUP_TEST_LINE_RE = re.compile('(\d{3})\s(.*)')

    def _get_available_tests(self):
        tests = glob.glob('???.out')
        tests += glob.glob('???.out.linux')
        tests = [t.replace('.linux', '') for t in tests]
        tests_list = [t[:-4] for t in tests if os.path.exists(t[:-4])]
        tests_list.sort()
        return tests_list

    def install_required_pkgs(self):
        arch = platform.processor()
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()

        pkgs = [
            'acl',
            'attr',
            'autoconf',
            'autopoint',
            'bc',
            'build-essential',
            'dbench',
            'dump',
            'gettext',
            'libblkid-dev',
            'libicu-dev',
            'libssl-dev',
            'libtool',
            'patchutils',
            'pkgconf',
            'quota',
            'uuid-dev'
        ]

        gcc = 'gcc' if arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        if series not in ['precise', 'trusty']:
            pkgs.append('btrfs-progs')
        if series not in ['precise', 'trusty', 'xenial']:
            pkgs.append('duperemove')

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def _run_sub_test(self, test):
        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'fstests-bld', 'xfstests-dev'))
        output = utils.system_output('./check %s' % test,
                                     ignore_status=True,
                                     retain_output=True)
        lines = output.split('\n')
        result_line = lines[-1]

        if self.NA_RE.match(result_line):
            detail_line = lines[-3]
            match = self.NA_DETAIL_RE.match(detail_line)
            if match is not None:
                error_msg = match.groups()[2]
            else:
                error_msg = 'Test dependency failed, test not run'
            raise error.TestNAError(error_msg)

        elif self.FAILED_RE.match(result_line):
            raise error.TestError('Test error, check debug logs for complete '
                                  'test output')

        elif self.PASSED_RE.match(result_line):
            return

        else:
            raise error.TestError('Could not assert test success or failure, '
                                  'assuming failure. Please check debug logs')

    def _get_groups(self):
        '''
        Returns the list of groups known to xfstests

        By reading the group file and identifying unique mentions of groups
        '''
        groups = []
        for l in open(os.path.join(self.srcdir, 'group')).readlines():
            m = self.GROUP_TEST_LINE_RE.match(l)
            if m is not None:
                groups = m.groups()[1].split()
                for g in groups:
                    if g not in groups:
                        groups.add(g)
        return groups


    def _get_tests_for_group(self, group):
        '''
        Returns the list of tests that belong to a certain test group
        '''
        tests = []
        for l in open(os.path.join(self.srcdir, 'group')).readlines():
            m = self.GROUP_TEST_LINE_RE.match(l)
            if m is not None:
                test = m.groups()[0]
                groups = m.groups()[1]
                if group in groups.split():
                    if test not in tests:
                        tests.append(test)
        return tests


    def _run_suite(self):
        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'fstests-bld', 'xfstests-dev'))
        exclusion = os.path.join(self.srcdir, 'xfstests-bld', 'test-appliance', 'files',
                                 'root', 'fs', 'btrfs', 'exclude')
        utils.system_output('./check -E %s -g auto -x dangerous' % exclusion,
                            ignore_status=True,
                            retain_output=True)

    def initialize(self):
        pass

    def setup(self):
        '''
        Sets up the environment necessary for running xfstests
        '''
        self.install_required_pkgs()

        utils.system_output('useradd -m fsgqa || true', retain_output=True)
        utils.system_output('grep -q fsgqa /etc/sudoers || echo \"fsgqa    ALL=(ALL)NOPASSWD: ALL\" >> /etc/sudoers', retain_output=True)

        self.job.require_gcc()

        canonical.setup_proxy()

        print("Fetching xfstests..")
        os.chdir(self.srcdir)
        shutil.rmtree('xfstests-bld', ignore_errors=True)
        utils.system('git clone https://github.com/tytso/xfstests-bld')

        os.chdir(os.path.join(self.srcdir, 'xfstests-bld'))
        commit_bld = '8672804daa67855739592070e1732991179c2ba9'
        print("Using head commit for xfstests-bld " + commit_bld)
        utils.system('git reset --hard ' + commit_bld)

        print("Building tests...")
        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'fstests-bld'))
        utils.system('./get-all')
        utils.system('./build-all')

        logging.debug("Available tests in srcdir: %s" %
                      ", ".join(self._get_available_tests()))

    def create_partitions(self, filesystem):
        print('/bin/bash %s/create-test-partitions %s %s' % (self.bindir, os.environ['XFSTESTS_TEST_DRIVE'], filesystem))
        return utils.system('/bin/bash %s/create-test-partitions %s %s' % (self.bindir, os.environ['XFSTESTS_TEST_DRIVE'], filesystem))

    def unmount_partitions(self):
        for mnt_point in [os.environ['SCRATCH_MNT'], os.environ['TEST_DIR']]:
            utils.system('umount %s' % mnt_point, ignore_status=True)

    def run_once(self, test_name, filesystem='btrfs', test_number='000', single=False, skip_dangerous=True):
        if test_name == 'setup':
            return

        os.chdir(self.srcdir)
        if single:
            if test_number == '000':
                self.unmount_partitions()
                self.create_partitions(filesystem)
                logging.debug('Dummy test to setup xfstests')
                return

            if test_number not in self._get_available_tests():
                raise error.TestError('test file %s not found' % test_number)

            if skip_dangerous:
                if test_number in self._get_tests_for_group('dangerous'):
                    raise error.TestNAError('test is dangerous, skipped')

            logging.debug("Running test: %s" % test_number)
            self._run_sub_test(test_number)

        else:
            self.create_partitions(filesystem)
            self._run_suite()
            self.unmount_partitions()
