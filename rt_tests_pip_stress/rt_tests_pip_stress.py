import multiprocessing
import os
import platform
import re
import shutil
from autotest.client import canonical, test, utils
from autotest.client.shared import error

class rt_tests_pip_stress(test.test):
    version = 1

    def initialize(self):
        self.flavour = re.split('-\d*-', platform.uname()[2])[-1]
        self.arch = platform.processor()

    def install_required_pkgs(self):
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()

        pkgs = [
            'build-essential',
            'git',
            'libnuma-dev',
        ]
        gcc = 'gcc' if self.arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    # setup
    #
    #    Automatically run when there is no autotest/client/tmp/<test-suite> directory
    #
    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()
        os.chdir(self.srcdir)
        shutil.rmtree('rt-tests', ignore_errors=True)
        canonical.setup_proxy()
        branch = 'main'
        cmd = 'git clone -b {} https://git.kernel.org/pub/scm/utils/rt-tests/rt-tests.git'.format(branch)
        utils.system_output(cmd, retain_output=True)

        # Print test suite HEAD SHA1 commit id for future reference
        os.chdir(os.path.join(self.srcdir, 'rt-tests'))
        title_local = utils.system_output("git log --oneline -1 | sed 's/(.*)//'", retain_output=False, verbose=False)
        title_upstream = utils.system_output("git log --oneline | grep -v SAUCE | head -1", retain_output=False, verbose=False)
        print("Latest commit in '{}' branch: {}".format(branch, title_local))
        print("Latest upstream commit: {}".format(title_upstream))

        try:
            nprocs = '-j' + str(multiprocessing.cpu_count())
        except:
            nprocs = ''
        utils.make(nprocs)


    # run_once
    #
    #    Driven by the control file for each individual test.
    #
    #    Runs pip_stress. This is mainly for data gathering purposes for now, 
    #    but there is a pass/fail on execution time. The test should complete 
    #    almost immediately, so it has a timeout of 1s to show if there is a failure.
    #
    def run_once(self, test_name, args='', exit_on_error=True):
        if test_name == 'setup':
            return

        utils.system_output(self.srcdir + '/rt-tests/pip_stress ' + args, timeout=1, retain_output=True)

        return
