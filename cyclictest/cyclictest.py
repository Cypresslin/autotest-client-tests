import os
import platform
from autotest.client import test
from autotest.client.shared import utils


class cyclictest(test.test):
    version = 2
    preserve_srcdir = True

    # git://git.kernel.org/pub/scm/linux/kernel/git/tglx/rt-tests.git
    def initialize(self):
        pass

    def install_required_pkgs(self):
        arch   = platform.machine()
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()

        pkgs = [
            'build-essential',
        ]
        gcc = 'gcc' if arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()
        os.chdir(self.srcdir)
        utils.make()

    def run_once(self, test_name, args='-t 10 -l 100000'):
        if test_name == 'setup':
            return
        utils.system(self.srcdir + '/cyclictest ' + args)
