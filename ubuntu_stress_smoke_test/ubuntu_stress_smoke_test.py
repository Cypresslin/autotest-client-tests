#
#
import multiprocessing
import os
from autotest.client                        import test, utils
from autotest.client.shared                 import error
import platform
import shutil

class ubuntu_stress_smoke_test(test.test):
    version = 1

    def get_codename(self):
        try:
            for line in open('/etc/lsb-release').read().split('\n'):
                if line.startswith('DISTRIB_CODENAME='):
                    return line.split('=')[1].replace('"','')
            return 'unknown'
        except:
            return 'unknown'

    def install_required_pkgs(self):
        arch   = platform.processor()

        pkgs = [
            'apparmor',
            'build-essential',
            'git',
            'libaio-dev',
            'libapparmor-dev',
            'libattr1-dev',
            'libbsd-dev',
            'libkeyutils-dev',
            'zlib1g-dev',
        ]

        codename = self.get_codename()
        cgroup_tool = 'cgroup-bin' if codename in [ 'precise', 'trusty' ] else 'cgroup-tools'
        pkgs.append(cgroup_tool)

        gcc = 'gcc' if arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def initialize(self):
        pass

    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()
        os.chdir(self.srcdir)
        shutil.rmtree('stress-ng', ignore_errors=True)
        cmd = 'git clone --depth=1 https://git.launchpad.net/~canonical-kernel-team/+git/stress-ng'
        self.results = utils.system_output(cmd, retain_output=True)

        # Print test suite HEAD SHA1 commit id for future reference
        os.chdir(os.path.join(self.srcdir, 'stress-ng'))
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

        try:
            nprocs = '-j' + str(multiprocessing.cpu_count())
        except:
            nprocs = ''
        utils.make(nprocs)

    def run_once(self, test_name):
        if test_name == 'setup':
            return
        elif test_name == 'setup-check':
            cmd = '%s/ubuntu_stress_smoke_test_checks.sh' % (self.bindir)
            utils.system_output(cmd, retain_output=True)
            return
        elif test_name == 'setup-init':
            cmd = '%s/ubuntu_stress_smoke_test_init.sh' % (self.bindir)
            utils.system_output(cmd, retain_output=True)
            return


        if os.uname()[1] == '202008-28164-ZCU106':
            raise error.TestFail('Test marked as failed for ZCU106 as requested by portias, dev test hang (LP: #1998738)')
        os.chdir(os.path.join(self.srcdir, 'stress-ng'))
        cmd = '%s/ubuntu_stress_single_smoke_test.sh %s' % (self.bindir, test_name)
        self.results = utils.system_output(cmd, retain_output=True)

# vi:set ts=4 sw=4 expandtab syntax=python:
