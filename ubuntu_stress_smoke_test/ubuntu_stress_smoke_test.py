#
#
import multiprocessing
import os
from autotest.client                        import test, utils
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
        arch   = platform.machine()

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


        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def initialize(self):
        pass


    def setup(self):
        '''
        We used to run code in build_source() here. Since we want to bail out early
        if the requirement in ubuntu_stress_smoke_test_checks.sh does not met, we
        can't build source here anymore. setup() will be triggered after initalize()
        There is no chace to run check before setup(), this is an ugly hack we need
        to keep until we have a better solution.
        '''
        pass


    def build_source(self):
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()
        os.chdir(self.srcdir)
        shutil.rmtree('stress-ng', ignore_errors=True)
        branch = 'sru'
        if series in ['trusty']:
            branch = 'sru-trusty'
        cmd = 'git clone --depth=1 https://git.launchpad.net/~canonical-kernel-team/+git/stress-ng -b {}'.format(branch)
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
        if test_name == 'setup-test':
            self.install_required_pkgs()
            self.build_source()
            return
        elif test_name == 'setup-check':
            cmd = '%s/ubuntu_stress_smoke_test_checks.sh' % (self.bindir)
            utils.system_output(cmd, retain_output=True)
            return
        elif test_name == 'setup-init':
            cmd = '%s/ubuntu_stress_smoke_test_init.sh' % (self.bindir)
            utils.system_output(cmd, retain_output=True)
            return


        os.chdir(os.path.join(self.srcdir, 'stress-ng'))
        cmd = '%s/ubuntu_stress_single_smoke_test.sh %s' % (self.bindir, test_name)
        self.results = utils.system_output(cmd, retain_output=True)

# vi:set ts=4 sw=4 expandtab syntax=python:
