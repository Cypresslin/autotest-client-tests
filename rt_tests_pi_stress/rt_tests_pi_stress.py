import multiprocessing
import os
import platform
import re
import shutil
from autotest.client import canonical, test, utils
from autotest.client.shared import error

class rt_tests_pi_stress(test.test):
    version = 1

    def initialize(self):
        self.flavour = re.split('-\d*-', platform.uname()[2])[-1]
        self.arch = platform.machine()

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
    #    Runs pi_stress for 60 seconds. This is just for data gathering purposes for now.
    #
    def run_once(self, test_name, args=' -D 60 -m', exit_on_error=True):
        if test_name == 'setup':
            return
        
        # Set performance governor (only on x86_64 for now)
        if self.arch == 'x86_64':
            self.results = utils.system_output('cpupower frequency-set --governor performance')
        
        # Disable RT throttling
        self.results = utils.system_output('sysctl -w kernel.sched_rt_runtime_us=-1')

        utils.system_output('pi_stress ' + args, retain_output=True)

        return
