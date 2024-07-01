#
#
import os
import platform
import re
from autotest.client                        import test, utils
from autotest.client.shared                 import error

class ubuntu_kselftests_ftrace(test.test):
    version = 1

    def install_required_pkgs(self):
        '''Function to install necessary packages.'''
        pkgs = [
            'debhelper',
            'devscripts',
            'dpkg-dev',
            'git',
        ]
        gcc = 'gcc' if self.arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        utils.system_output(cmd, retain_output=True)

    def initialize(self):
        self.arch = platform.processor()
        self.flavour = re.split('-\d*-', platform.uname()[2])[-1]
        try:
            self.series = platform.dist()[2]
        except AttributeError:
            import distro
            self.series = distro.codename()
        self.kv = platform.release().split(".")[:2]
        self.kv = int(self.kv[0]) * 100 + int(self.kv[1])

    def download(self):
        '''Function to download kernel source.'''
        cmd = "dpkg -S /lib/modules/" + platform.release() + "/kernel | cut -d: -f 1 | cut -d, -f 1"
        pkg = os.popen(cmd).readlines()[0].strip()
        utils.system("apt-get source --download-only " + pkg)

    def extract(self):
        '''Function to extract kernel source.'''
        os.system("rm -rf linux/")
        utils.system("dpkg-source -x linux*dsc linux")

    def setup(self):
        '''Function to setup the test environment.'''
        self.install_required_pkgs()
        self.job.require_gcc()
        os.chdir(self.srcdir)

        # Use a local repo for manual testing. If it does not exist, then clone from the master
        # repository.
        #
        if not os.path.exists('linux'):
            self.download()
            self.extract()

            # clean source tree so changes from debian.foo/reconstruct
            # (e.g. deleting files) are applied
            os.chdir('linux')
            cmd = 'fakeroot debian/rules clean'
            utils.system(cmd)
            os.chdir(self.srcdir)

            #
            # Disable new ftrace tests that don't work reliably across
            # architectures because of various symbols being checked
            #
            filenames = [
                'ftrace/func_stack_tracer.tc',
                'ftrace/func-filter-glob.tc',
                'trigger/inter-event/trigger-inter-event-combined-hist.tc',
                'trigger/inter-event/trigger-synthetic-event-createremove.tc',
                'trigger/trigger-hist.tc',
                'trigger/trigger-trace-marker-hist.tc',
                'kprobe/probepoint.tc',
                'kprobe/kprobe_module.tc',
            ]

            for fn in filenames:
                fn = 'linux/tools/testing/selftests/ftrace/test.d/' + fn
                if os.path.exists(fn):
                    os.remove(fn)

            # Build header first (LP: #2031400)
            if not self.series in ['trusty', 'xenial', 'bionic', 'focal']:
                cmd = "make -C linux/ headers"
                utils.system_output(cmd, retain_output=True)


    def run_once(self, test_name):
        if test_name == 'setup':
            return
        if test_name.endswith('-build'):
            os.chdir(self.srcdir)
            cmd = "make -C linux/tools/testing/selftests TARGETS={}".format(test_name.replace('-build', ''))
            utils.system_output(cmd, retain_output=True)
            return
        if test_name == 'ftrace:test.d--kprobe--multiple_kprobes.tc' and self.arch == 'riscv64' and self.series == 'noble':
            raise error.TestFail('Test marked as failed as it cause panic for N-RISCV (LP: #2070034)')

        category = test_name.split(':')[0]
        sub_test = test_name.split(':')[1]
        dir_root = os.path.join(self.srcdir, 'linux', 'tools', 'testing', 'selftests', 'ftrace')
        os.chdir(dir_root)
        # Run sub-tests with ftracetest script, convert test name back to path
        test = sub_test.replace('--', '/')
        cmd = './ftracetest -v {}'.format(test)
        result = utils.system_output(cmd, retain_output=True)

# vi:set ts=4 sw=4 expandtab syntax=python:
