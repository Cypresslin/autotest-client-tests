import multiprocessing
import os
import platform
import re
import shutil
from autotest.client import canonical, test, utils
from autotest.client.shared import error

class rt_tests_cyclictest(test.test):
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
    #    Runs cyclictest with 10 threads, for 100000 loops, priority set to 
    #    80 and an interval of 200us. It will fail if the max latency goes 
    #    over a specified latency.
    #
    def run_once(self, test_name, args='-t 10 -m -l 100000 -p 80 -i 200 -d 0 -q', exit_on_error=True):
        if test_name == 'setup':
            return
        
        # Set performance governor (only on x86_64 for now)
        if self.arch == 'x86_64':
            self.results = utils.system_output('cpupower frequency-set --governor performance')
        
        # Disable RT throttling
        self.results = utils.system_output('sysctl -w kernel.sched_rt_runtime_us=-1')
        
        latency_limit = 500
        if self.hostname in ['starlow', 'taycet', 'drapion', 'bunsen']:
            latency_limit = 120

        self.results = utils.system_output('cyclictest ' + args, retain_output=True)

        # Find the last contiguous block of lines that include "T:", 
        # which contains the final values for cyclictest.
        cyclictest_last_group = []
        block_started = False
        for line in reversed(self.results.splitlines()):
            if line.find("T:") >= 0:
                cyclictest_last_group.append(line)
                block_started = True
            elif block_started:
                break

        # Calculate the min/avg/max
        min_values = []
        avg_values = []
        max_values = []

        for line in cyclictest_last_group:
            min_value = int(re.search(r'Min:\s+(\d+)', line).group(1))
            avg_value = int(re.search(r'Avg:\s+(\d+)', line).group(1))
            max_value = int(re.search(r'Max:\s+(\d+)', line).group(1))
            
            min_values.append(min_value)
            avg_values.append(avg_value)
            max_values.append(max_value)

        max_latency = max(max_values)
        mean_latency = sum(avg_values) / float(len(avg_values))
        minimum_latency = min(min_values)

        # Print stats in format used by mass-scrape-influxdb.sh
        print("rt_tests_cyclictest_latency_maximum %.3f" % float(max_latency))
        print("rt_tests_cyclictest_latency_average %.3f" % float(mean_latency))
        print("rt_tests_cyclictest_latency_minimum %.3f" % float(minimum_latency))

        # Check if any max value is over latency limit
        # Only fail real-time kernels on high latency
        if max_latency > latency_limit and "realtime" in self.flavour:
            raise error.TestError('FAIL: Max latency over ' + str(latency_limit) + 'us.')

        return

