#
#
import os
import platform
import re
from autotest.client                        import test, utils
from autotest.client.shared                 import error

class ubuntu_kernel_selftests(test.test):
    version = 1

    def install_required_pkgs(self):
        '''Function to install necessary packages.'''
        pkgs = [
            'bc',           # For memory-hotplug
            'build-essential',
            'fuse',         # For memfd
            'kernel-wedge', # For "fakeroot debian/rules clean"
            'libcap-dev',   # For seccomp
            'libfuse-dev',  # For memfd
            'pkg-config',
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

            # tweak sleep wake alarm time to 30 seconds as 5 is a bit too small
            #
            fn = 'linux/tools/testing/selftests/breakpoints/step_after_suspend_test.c'
            if os.path.exists(fn):
                cmd = 'sed -i "s/tv_sec = 5;/tv_sec = 30;/" ' + fn
                utils.system(cmd)
            # currently disable step_after_suspend_test as this breaks ssh'd login
            # connections to the test VMs and real H/W
            fn = 'linux/tools/testing/selftests/breakpoints/Makefile'
            if os.path.exists(fn):
                cmd = 'sed -i "s/\(.* .\?= step_after_suspend_test\)/#\\1/" ' + fn
                utils.system(cmd)
                # LP #1680507
                cmd = 'sed -i /breakpoint_test_arm64/d ' + fn
                utils.system(cmd)

            #
            # disable rtctest, LP: #1659333
            #   this hangs xenial host servers when running in a VM,
            #   so for now disable this test. Urgh, dirty hack
            #
            fn = 'linux/tools/testing/selftests/timers/Makefile'
            if os.path.exists(fn):
                cmd = 'sed -i "s/threadtest rtctest/threadtest/" ' + fn
                utils.system(cmd)
            #
            # newer kernels have the rtctest in the rtc subdirectory
            #
            fn = 'linux/tools/testing/selftests/rtc/Makefile'
            if os.path.exists(fn):
                cmd = 'sed -i "s/ rtctest//" ' + fn
                utils.system(cmd)

            #
            # update fix CPU hotplug test, new and old versions
            #
            print("Updating CPU hotplug test")
            fn = "linux/tools/testing/selftests/cpu-hotplug/cpu-on-off-test.sh"
            if os.path.exists(fn) and 'present_cpus=' not in open(fn).read():
                cmd = 'cp %s/cpu-on-off-test.sh %s' % (self.bindir, fn)
                utils.system(cmd)
            else:
                fn = "linux/tools/testing/selftests/cpu-hotplug/on-off-test.sh"
                if os.path.exists(fn) and 'present_cpus=' not in open(fn).read():
                    cmd = 'cp %s/cpu-on-off-test.sh %s' % (self.bindir, fn)
                    utils.system(cmd)

            #
            # cpu hotplug test might fail on Azure instances because Hyper-V
            # does not allow it.
            #
            if self.flavour in ['azure', 'azure-fips']:
                print("Disabling CPU hotplug test")
                fn = 'linux/tools/testing/selftests/cpu-hotplug/cpu-on-off-test.sh'
                mk = 'linux/tools/testing/selftests/cpu-hotplug/Makefile'
                if os.path.exists(fn):
                    cmd = 'sed -i "s/ cpu-on-off-test.sh//" ' + mk
                    utils.system(cmd)

            #
            # ptrace/vmaccess was introduced in 5.7-rc1 and is broken ATM,
            # see https://lkml.org/lkml/2020/4/9/648
            #
            fn = 'linux/tools/testing/selftests/ptrace/vmaccess.c'
            mk = 'linux/tools/testing/selftests/ptrace/Makefile'
            if os.path.exists(fn):
                print("Disabling ptrace/vmacces")
                cmd = 'sed -i "s/ vmaccess//" ' + mk
                utils.system(cmd)

            #
            # memory hotplug test will fail on arm and several cloud platforms from 5.6+
            # as it was enabled in 5.6 but needs memory that does not
            # have boot time pages in the regions to be offlined and
            # current test hardware cannot guarantee that constraint.
            # Except ARM, also all cloud platforms on amd64 seems to have unmovable
            # pages which makes memory hotplug failing.
            #
            if self.arch.startswith('arm') or self.arch == 'aarch64' or \
               self.flavour in ['aws', 'azure', 'azure-fips']:
                print("Disabling memory hotplug test")
                fn = 'linux/tools/testing/selftests/memory-hotplug/mem-on-off-test.sh'
                mk = 'linux/tools/testing/selftests/memory-hotplug/Makefile'
                if os.path.exists(fn):
                    cmd = 'sed -i "s/ mem-on-off-test.sh//" ' + mk
                    utils.system(cmd)

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

        category = test_name.split(':')[0]
        sub_test = test_name.split(':')[1]
        dir_root = os.path.join(self.srcdir, 'linux', 'tools', 'testing', 'selftests')
        os.chdir(dir_root)
        cmd = "make run_tests -C {} TEST_PROGS={} TEST_GEN_PROGS='' TEST_CUSTOM_PROGS=''".format(category, sub_test)
        result = utils.system_output(cmd, retain_output=True)

        # Old pattern for Xenial
        pattern = re.compile('selftests: *(?P<case>[\w\-\.]+) \[FAIL\]\n')
        if re.search(pattern, result):
            raise error.TestError(test_name + ' failed.')
        # If the test was not end by previous check, check again with new pattern
        pattern = re.compile('not ok [\d\.]* selftests: {}: {} # (?!.*SKIP)'.format(category, sub_test))
        if re.search(pattern, result):
            raise error.TestError(test_name + ' failed.')


# vi:set ts=4 sw=4 expandtab syntax=python:
