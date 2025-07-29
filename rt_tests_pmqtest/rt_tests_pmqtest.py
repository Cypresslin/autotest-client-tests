import multiprocessing
import os
import platform
import re
import shutil
from autotest.client import canonical, test, utils
from autotest.client.shared import error

class rt_tests_pmqtest(test.test):
    version = 1

    def initialize(self):
        self.flavour = re.split('-\d*-', platform.uname()[2])[-1]
        self.arch = platform.processor()
        self.hostname = os.uname()[1]

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
    #    Runs pmqtest for 60 seconds. This will fail if the max latency is over a specified limit.
    #
    def run_once(self, test_name, args='-Sp80 -i100 -d0 -q -D60', exit_on_error=True):
        if test_name == 'setup':
            return
        
        # Set performance governor
        self.results = utils.system_output('cpupower frequency-set --governor performance')
        
        # Disable RT throttling
        self.results = utils.system_output('sysctl -w kernel.sched_rt_runtime_us=-1')
        
        latency_limit = 500

        self.results = utils.system_output('pmqtest ' + args, retain_output=True)

        # Extract results lines (contain "Max")
        results_lines = [line for line in self.results.splitlines() if "Max" in line]
        
        # Calculate the min/avg/max
        min_values = []
        avg_values = []
        max_values = []

        for line in results_lines:
            min_value = int(re.search(r'Min\s+(\d+)', line).group(1))
            avg_value = int(re.search(r'Avg\s+(\d+)', line).group(1))
            max_value = int(re.search(r'Max\s+(\d+)', line).group(1))
            
            min_values.append(min_value)
            avg_values.append(avg_value)
            max_values.append(max_value)

        max_latency = max(max_values)
        mean_latency = sum(avg_values) / float(len(avg_values))
        min_latency = min(min_values)

        print("rt_tests_pmqtest_latency_maximum %.3f" % float(max_latency))
        print("rt_tests_pmqtest_latency_average %.3f" % float(mean_latency))
        print("rt_tests_pmqtest_latency_minimum %.3f" % float(min_latency))

        # Check if any max value is over latency limit
        # Only fail real-time kernels on high latency
        if max_latency > latency_limit and "realtime" in self.flavour:
            raise error.TestError('FAIL: Max latency over ' + str(latency_limit) + 'us.')

        return
