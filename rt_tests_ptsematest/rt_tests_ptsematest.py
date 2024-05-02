import multiprocessing
import os
import platform
import re
import shutil
from autotest.client import canonical, test, utils
from autotest.client.shared import error

class rt_tests_ptsematest(test.test):
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
    #    Runs ptsematest with one thread per processor, for 100000 loops, and 
    #    priority set to 80. It will fail if the max latency goes over a specified limit.
    #
    def run_once(self, test_name, args='-l 100000 -p 80 -S -q', exit_on_error=True):
        if test_name == 'setup':
            return
        
        latency_limit = 1000
        if self.hostname == 'starlow':
            latency_limit = 200
        elif self.hostname == 'ivysaur':
            latency_limit = 700

        self.results = utils.system_output(self.srcdir + '/rt-tests/ptsematest ' + args, retain_output=True)

        # Parse results
        max_values = []
        lines = self.results.split('\n')

        for line in lines:
            components = line.split(',')
            for component in components:
                if 'Max' in component:
                    # Extract the max latency for each thread
                    max_value = int(component.strip().split()[-1])
                    max_values.append(max_value)

        # Find the highest "Max" latency
        highest_max = max(max_values)
        print("Highest Max Latency:", highest_max)

        if highest_max > latency_limit:
            raise error.TestError('FAIL: Max latency over ' + str(latency_limit) + 'us.')

        return
