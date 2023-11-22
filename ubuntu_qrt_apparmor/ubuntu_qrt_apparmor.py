import os
import platform
import shutil
from autotest.client import test, utils

class ubuntu_qrt_apparmor(test.test):
    version = 1

    def install_required_pkgs(self):
        arch = platform.processor()

        pkgs = [
            'apparmor',
            'apparmor-profiles',
            'apparmor-utils',
            'apport',
            'attr',
            'devscripts',
            'execstack',
            'exim4',
            'gawk',
            'git',
            'libapparmor-dev',
            'libcap2-bin',
            'libcap-dev',
            'libdbus-1-dev',
            'libgtk2.0-dev',
            'libpam-apparmor',
            'python3',
            'python3-all-dev',
            'quilt',
            'sudo',
        ]
        gcc = 'gcc' if arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        if self.series == 'precise':
            for p in ['python-libapparmor', 'ruby1.8', 'libapparmor-perl']:
                pkgs.append(p)
        elif self.series in ['trusty', 'xenial', 'bionic', 'cosmic']:
            for p in ['python-libapparmor', 'python3-libapparmor', 'ruby', 'apparmor-easyprof', 'libapparmor-perl']:
                pkgs.append(p)
        elif self.series in ['focal', 'impish']:
            for p in ['python3-libapparmor', 'ruby', 'apparmor-easyprof', 'libapparmor-perl']:
                pkgs.append(p)
        else:
            for p in ['python3-libapparmor', 'ruby']:
                pkgs.append(p)


        if self.series in ['precise']:
            pkgs.append('netcat')
        else:
            pkgs.append('netcat-openbsd')

        if self.series in ['precise', 'trusty', 'xenial', 'bionic', 'focal']:
            pkgs.append('pyflakes')
            pkgs.append('python-pexpect')
        else:
            pkgs.append('pyflakes3')
            pkgs.append('python3-pexpect')
            pkgs.append('python3-notify2')
            pkgs.append('python3-psutil')

        if self.series not in ['trusty', 'xenial', 'bionic', 'focal', 'jammy', 'lunar']:
            pkgs.append('liburing-dev') # LP: #2044230

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

        # During execution on baremetal, apparmor.service is restarted too
        # quickly too fast, and that triggers 'start-limit-hit' threshold error:
        # runtime increase the threshold.
        if self.series == 'jammy':
            aadir = '/run/systemd/system.control/apparmor.service.d'
            cmd = 'mkdir -p %s' % (aadir)
            utils.system_output(cmd, retain_output=True)
            cmd = 'mv %s/10-StartLimitBurst.conf %s' % (self.bindir, aadir)
            utils.system_output(cmd, retain_output=True)
            cmd = 'systemctl daemon-reload'
            utils.system_output(cmd, retain_output=True)
            cmd = 'systemctl show --property=StartLimitBurst apparmor.service'
            burst = utils.system_output(cmd, retain_output=False, verbose=False)
            print("apparmor.service StartLimitBurst: %s" % (burst))

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

    def run_once(self, test_name):
        if test_name == 'setup':
            return
        elif test_name == 'cleanup':
            # Tear down StartLimitBurst threshold increase
            if self.series == 'jammy':
                aadir = '/run/systemd/system.control/apparmor.service.d'
                cmd = 'rm -f %s/10-StartLimitBurst.conf' % (aadir)
                utils.system_output(cmd, retain_output=True)
                cmd = 'systemctl daemon-reload'
                utils.system_output(cmd, retain_output=True)
                cmd = 'systemctl show --property=StartLimitBurst apparmor.service'
                burst = utils.system_output(cmd, retain_output=False, verbose=False)
                print("apparmor.service StartLimitBurst: %s" % (burst))
            return

        scripts = os.path.join(self.srcdir, 'qa-regression-testing', 'scripts')
        os.chdir(scripts)

        # Workaround for LP: #2000062
        cleanup = False
        if test_name == "ApparmorTestsuites.test_utils_testsuite":
            if not 'PYTHON' in os.environ:
                os.environ['PYTHON_VERSIONS'] = 'python3'
                print("Use python3 for ApparmorTestsuites.test_utils_testsuite test (LP: #2000062)")
                cleanup = True

        inter = 'python3'
        if self.series in ['precise', 'trusty', 'xenial', 'bionic', 'focal']:
            inter = 'python2'

        cmd = '%s ./test-apparmor.py -v %s' % (inter, test_name)
        self.results = utils.system_output(cmd, retain_output=True)

        # Workaround for LP: #2000062 (cleanup)
        if test_name == "tApparmorTestsuites.test_utils_testsuit" and cleanup:
            del os.environ['PYTHON_VERSIONS']

# vi:set ts=4 sw=4 expandtab:
