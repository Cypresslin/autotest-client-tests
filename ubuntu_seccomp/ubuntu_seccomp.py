#
#
import os
import platform
import shutil
from autotest.client                        import test, utils

class ubuntu_seccomp(test.test):
    version = 1

    def install_required_pkgs(self):
        arch   = platform.processor()

        pkgs = [
            'build-essential', 'git', 'libtool', 'build-essential', 'autoconf', 'valgrind', 'gperf',
        ]
        gcc = 'gcc' if arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def initialize(self):
        pass

    # setup
    #
    #    Automatically run when there is no autotest/client/tmp/<test-suite> directory
    #
    def setup(self):
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()
        self.install_required_pkgs()
        self.job.require_gcc()
        os.chdir(self.srcdir)
        shutil.rmtree('libseccomp', ignore_errors=True)
        cmd = "git clone https://github.com/seccomp/libseccomp.git"
        utils.system_output(cmd, retain_output=True)
        if series in ["trusty", "xenial", "bionic"]:
            print("Pin libseccomp to e7e633c28a for releases <= Bionic (LP: #2125202)")
            os.chdir("libseccomp")
            cmd = "git reset e7e633c28aed5333b185bfc0ad6f8d70b5fc20be --hard"
            utils.system_output(cmd, retain_output=True)

        # Print test suite HEAD SHA1 commit id for future reference
        os.chdir(os.path.join(self.srcdir, 'libseccomp'))
        sha1 = None
        if os.path.isdir('.git'):
            sha1 = utils.system_output('git rev-parse --short HEAD', retain_output=False, verbose=False)
        elif os.path.isfile('head-sha1.txt'):
            with open('head-sha1.txt') as f:
                sha1 = f.readline()

        if sha1:
            print("Test suite HEAD SHA1: {}".format(sha1))
        else:
            print("Unable to get HEAD SHA1, proceed testing anyway.")

        autogen = self.srcdir + '/libseccomp/autogen.sh'
        self.results = utils.system_output(autogen, retain_output=True)
        utils.configure()
        utils.make('check-build')

    # run_once
    #
    #    Driven by the control file for each individual test.
    #
    def run_once(self, test_name):
        if test_name == 'setup':
            return
        os.chdir(os.path.join(self.srcdir, 'libseccomp', 'tests'))

        cmd = 'time ./regression -b {}'.format(test_name)
        utils.system_output(cmd, verbose=False, retain_output=True)

# vi:set ts=4 sw=4 expandtab syntax=python:
