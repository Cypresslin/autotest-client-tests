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
            'rt-tests',
        ]
        gcc = 'gcc' if self.arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        # Install tools for cpupower
        tools_pkg = "linux-tools-" + self.flavour
        pkgs.append(tools_pkg)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    # setup
    #
    #    Automatically run when there is no autotest/client/tmp/<test-suite> directory
    #
    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()

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
        
        # Set performance governor
        self.results = utils.system_output('cpupower frequency-set --governor performance')
        
        # Disable RT throttling
        self.results = utils.system_output('sysctl -w kernel.sched_rt_runtime_us=-1')

        utils.system_output('pip_stress ' + args, timeout=1, retain_output=True)

        return
