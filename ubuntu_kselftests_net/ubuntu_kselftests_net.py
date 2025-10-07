#
#
import os
import platform
import re
from autotest.client                        import test, utils
from autotest.client.shared                 import error

class ubuntu_kselftests_net(test.test):
    version = 1

    def install_required_pkgs(self):
        '''Function to install necessary packages.'''
        pkgs = [
            'build-essential',
            'docutils-common',  # For bpf test build
            'ethtool',          # For net:udpgro_fwd.sh
            'iptables',         # For net:ip_defrag.sh
            'jq',               # For net:altnames.sh
            'kernel-wedge',     # For "fakeroot debian/rules clean"
            'libfuse-dev',      # For net:reuseport_bpf_numa
            'libnuma-dev',      # For net:reuseport_bpf_numa
            'libssl-dev',       # For net:tcp_mmap
            'net-tools',        # For net:rtnetlink.sh
            'pkg-config',
            'tcpdump',          # For net:cmsg_ipv6.sh
            'uuid-runtime',     # For net:rtnetlink.sh
        ]
        # For net:fib_tests.sh
        if not self.series in ['trusty', 'xenial', 'bionic']:
            pkgs.append('socat')
        # For net:altnames.sh
        if 'fips' not in self.flavour:
            # netsniff-ng depends on ntp, it will try to perorm a MD5 sum which is not allowed with FIPS kernels (LP: #2054609)
            pkgs.append('netsniff-ng')

        if not self.arch == 's390x':
            if not self.series in ['trusty', 'xenial', 'bionic', 'focal', 'jammy']:
                # With recent kernels BPF requires lld (LLVM-based linker) to
                # build the corresponding kernel selftests, so make sure this
                # package is installed (in the releases where it is available)
                # lld is not available for s390x
                pkgs.append('lld')

        # The modules-extra is required for net:rtnetlink.sh test
        if any(x in self.flavour for x in ['aws', 'azure', 'gcp', 'gke', 'ibm', 'oracle']) and self.kv < 617:
            if not (self.flavour == 'aws' and self.series == 'trusty'):
                pkgs.append('linux-modules-extra-' + platform.uname()[2])

        if self.kv >= 415:
            # extra packages for building bpf tests, which is required for some tests in net
            pkgs.extend(['libcap-dev', 'libelf-dev'])
            if self.kv == 504:
                # special case for B-5.4 (lp:1882559) / B-5.3 (lp:1845860)
                # clang on F is clang-10 but we need clang-9 (see commit 95f91d59642)
                # clang on E is clang-9, so it's ok to just check kv here
                pkgs.extend(['clang-9', 'llvm-9'])
            else:
                pkgs.extend(['clang', 'llvm'])

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        utils.system_output(cmd, retain_output=True)

    def initialize(self):
        self.arch = platform.machine()
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
        cmd = "dpkg -S /lib/modules/" + platform.release() + "/modules.builtin | cut -d: -f 1 | cut -d, -f 1"
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

            # net/txtimestamp.sh is very fragile, disable it
            #
            fn = 'linux/tools/testing/selftests/net/Makefile'
            if os.path.exists(fn):
                cmd = 'sed -i "/^TEST_PROGS += txtimestamp.sh$/d" ' + fn
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
            if "net" in test_name:
                cmds = []
                cmds.append("sh -c 'echo 1 > /proc/sys/net/ipv4/conf/all/accept_local'")
                # The net benchmarching tests (e.g. udpgso) can fail when
                # optmem limit is reached.
                # https://www.kernel.org/doc/html/latest/networking/msg_zerocopy.html#transmission
                # LP #1960907
                cmds.append("sh -c 'echo 2048000 > /proc/sys/net/core/optmem_max'")
                for cmd in cmds:
                    utils.system(cmd)

                if self.kv >= 415:
                    # net selftests use a module built by bpf selftests, bpf is available since bionic kernel
                    if self.kv == 504:
                        os.environ["CLANG"] = "clang-9"
                        os.environ["LLC"] = "llc-9"
                        os.environ["LLVM_OBJCOPY"] = "llvm-objcopy-9"
                        os.environ["LLVM_READELF"] = "llvm-readelf-9"
                    cmd = "make -C linux/tools/testing/selftests TARGETS=bpf SKIP_TARGETS= KDIR=/usr/src/linux-headers-{}".format(platform.release())
                    # keep running selftests/net, even if selftests/bpf build fails
                    utils.system(cmd, ignore_status=True)
            cmd = "make -C linux/tools/testing/selftests TARGETS={}".format(test_name.replace('-build', ''))
            utils.system_output(cmd, retain_output=True)
            return

        category = test_name.split(':')[0]
        sub_test = test_name.split(':')[1]
        dir_root = os.path.join(self.srcdir, 'linux', 'tools', 'testing', 'selftests')
        os.chdir(dir_root)
        cmd = "make run_tests -C {} TEST_PROGS={} TEST_GEN_PROGS='' TEST_CUSTOM_PROGS=''".format(category, sub_test)
        result = utils.system_output(cmd, retain_output=True)

        # The output of test_bpf.sh / test_blackhole_dev.sh test will be in the dmesg
        kernel_module_tests = {'test_bpf.sh': 'CONFIG_TEST_BPF',
                               'test_blackhole_dev.sh': 'CONFIG_TEST_BLACKHOLE_DEV'}
        if sub_test in kernel_module_tests.keys():
            output = utils.system_output('dmesg', retain_output=True)
            if not output:
                print("Looks like there's no dmesg output, checking for {}...".format(kernel_module_tests[sub_test]))
                cmd = "grep ^{} /boot/config-$(uname -r)".format(kernel_module_tests[sub_test])
                if not utils.system_output(cmd, verbose=False, ignore_status=True):
                    print("{} not enabled.".format(kernel_module_tests[sub_test]))

        # Old pattern for Xenial
        pattern = re.compile('selftests: *(?P<case>[\w\-\.]+) \[FAIL\]\n')
        if re.search(pattern, result):
            raise error.TestError(test_name + ' failed.')
        # If the test was not end by previous check, check again with new pattern
        pattern = re.compile('not ok [\d\.]* selftests: {}: {} # (?!.*SKIP)'.format(category, sub_test))
        if re.search(pattern, result):
            raise error.TestError(test_name + ' failed.')


# vi:set ts=4 sw=4 expandtab syntax=python:
