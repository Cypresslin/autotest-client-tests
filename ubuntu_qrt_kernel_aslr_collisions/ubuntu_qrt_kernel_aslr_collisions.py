import os
import platform
import shutil
from autotest.client import test, utils

class ubuntu_qrt_kernel_aslr_collisions(test.test):
    version = 1

    def install_required_pkgs(self):
        arch = platform.processor()

        pkgs = [
            'git', 'build-essential', 'libcap2-bin', 'gawk', 'execstack', 'exim4', 'libcap-dev',
        ]
        gcc = 'gcc' if arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def initialize(self):
        try:
            self.series = platform.dist()[2]
        except AttributeError:
            import distro
            self.series = distro.codename()

    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()
        os.chdir(self.srcdir)
        # Kernel QA Automation already copies the qa-regression-testing
        # repo over to the SUT(system under test) via rsync+ssh.
        # This resolves issues with extremely long git clones. Causing
        # tests to fail.
        # If qa-regression-testing exists in the SUT Homedir, just move
        # it over to the autotest workarea. If not, then clone it
        targetpath = os.path.expanduser("~") + "/qa-regression-testing"
        if os.path.isdir(targetpath):
            cmd = 'mv %s .' % targetpath
        else:
            # If the directory does not exist, then lets clone it as this test
            # is probably being run by someone triaging a problem.
            shutil.rmtree('qa-regression-testing', ignore_errors=True)
            cmd = 'git clone --depth 1 https://git.launchpad.net/qa-regression-testing'
        self.results = utils.system_output(cmd, retain_output=True)
        # Print test suite HEAD SHA1 commit id for future reference
        os.chdir(os.path.join(self.srcdir, 'qa-regression-testing'))
        sha1 = utils.system_output('git rev-parse --short HEAD', retain_output=False, verbose=False)
        print("Test suite HEAD SHA1: {}".format(sha1))

    def run_once(self, test_name):
        if test_name == 'setup':
            return

        scripts = os.path.join(self.srcdir, 'qa-regression-testing', 'scripts')
        os.chdir(scripts)

        inter = 'python3'
        if self.series in ['precise', 'trusty', 'xenial', 'bionic', 'focal']:
            inter = 'python2'

        cmd = '%s ./test-kernel-aslr-collisions.py -v %s' % (inter, test_name)
        self.results = utils.system_output(cmd, retain_output=True)


# vi:set ts=4 sw=4 expandtab:
