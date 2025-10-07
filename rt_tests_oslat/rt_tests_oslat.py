import multiprocessing
import os
import platform
import re
import shutil
from autotest.client import canonical, test, utils
from autotest.client.shared import error

class rt_tests_oslat(test.test):
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
    #    Runs oslat for 600 seconds. This is just for data gathering purposes for now.
    #
    def run_once(self, test_name, args='--cpu-list 2-7 --rtprio 1 --duration 600 -q', exit_on_error=True):
        if test_name == 'setup':
            return
        
        # Set performance governor (only on x86_64 for now)
        if self.arch == 'x86_64':
            self.results = utils.system_output('cpupower frequency-set --governor performance')

        # Disable RT throttling
        self.results = utils.system_output('sysctl -w kernel.sched_rt_runtime_us=-1')

        self.results = utils.system_output('oslat ' + args, retain_output=True)

        # Determine min/avg/max latencies
        min_match = re.search(r"Minimum:\s+([0-9.\s]+)", self.results)
        avg_match = re.search(r"Average:\s+([0-9.\s]+)", self.results)
        max_match = re.search(r"Maximum:\s+([0-9.\s]+)", self.results)

        minimums = list(map(float, min_match.group(1).split()))
        averages = list(map(float, avg_match.group(1).split()))
        maximums = list(map(float, max_match.group(1).split()))

        oslat_minumum = sum(minimums) / len(minimums)
        oslat_average = sum(averages) / len(averages)
        oslat_maximum = max(maximums)

        # Print stats in format used by mass-scrape-influxdb.sh
        print("rt_tests_oslat_latency_minimum %.3f" % float(oslat_minumum))
        print("rt_tests_oslat_latency_average %.3f" % float(oslat_average))
        print("rt_tests_oslat_latency_maximum %.3f" % float(oslat_maximum))

        return
