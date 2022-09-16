#
#
from autotest.client import test, utils
from autotest.client.shared import error
import platform
import os

class ubuntu_bpf(test.test):
    version = 1

    def install_required_pkgs(self):
        arch   = platform.processor()

        pkgs = [
            'build-essential',
            'debhelper',
            'docutils-common',
            'git',
            'libcap-dev',
            'libelf-dev',
        ]
        gcc = 'gcc' if arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        if self.series == 'focal':
            if self.kv.startswith('5.6.0'):
                # Specical case of F-oem-5.6 (lp:1879360)
                pkgs.extend(['clang-10', 'llvm-10'])
            else:
                pkgs.extend(['clang-9', 'llvm-9'])
        elif self.series == 'bionic':
            if self.kv.startswith('5.4.0') or self.kv.startswith('5.3.0'):
                # Special case for B-5.4 (lp:1882559) B-5.3 (lp:1845860)
                pkgs.extend(['clang-9', 'llvm-9'])
            else:
                pkgs.extend(['clang', 'llvm'])
        else:
            pkgs.extend(['clang', 'llvm', 'lld'])

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def initialize(self):
        try:
            self.series = platform.dist()[2]
        except AttributeError:
            import distro
            self.series = distro.codename()
        self.kv = platform.release()
        pass

    def download(self):
        cmd = "dpkg -S /lib/modules/" + self.kv + "/kernel | cut -d: -f 1 | cut -d, -f 1"
        pkg = os.popen(cmd).readlines()[0].strip()
        utils.system("apt-get source --download-only " + pkg)

    def extract(self):
        os.system("rm -rf linux/")
        utils.system("dpkg-source -x linux*dsc linux")

    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()

        os.chdir(self.srcdir)
        if not os.path.exists('linux'):
            self.download()
        # Assist local testing by restoring the linux repo to vanilla.
        self.extract()

        # clean source tree so changes from debian.foo/reconstruct
        # (e.g. deleting files) are applied
        os.chdir('linux')
        cmd = 'fakeroot debian/rules clean'
        utils.system(cmd)

        os.chdir(self.srcdir)

        #
        # llvm10 breaks bpf test_maps, revert to llvm9 instead
        #
        if self.series == 'focal':
            if self.kv.startswith('5.6.0'):
                os.environ["CLANG"] = "clang-10"
                os.environ["LLC"] = "llc-10"
                os.environ["LLVM_OBJCOPY"] = "llvm-objcopy-10"
                os.environ["LLVM_READELF"] = "llvm-readelf-10"
            else:
                os.environ["CLANG"] = "clang-9"
                os.environ["LLC"] = "llc-9"
                os.environ["LLVM_OBJCOPY"] = "llvm-objcopy-9"
                os.environ["LLVM_READELF"] = "llvm-readelf-9"
        elif self.series == 'bionic':
            if self.kv.startswith('5.4.0') or self.kv.startswith('5.3.0'):
                os.environ["CLANG"] = "clang-9"
                os.environ["LLC"] = "llc-9"
                os.environ["LLVM_OBJCOPY"] = "llvm-objcopy-9"
                os.environ["LLVM_READELF"] = "llvm-readelf-9"

        cmd = '-C linux/tools/testing/selftests TARGETS=bpf SKIP_TARGETS= clean all KDIR=/usr/src/linux-headers-{}'.format(platform.release())
        utils.make(cmd)

    def run_once(self, test_name):
        if test_name == 'setup':
            return
        elif test_name == 'config_check':
            meaning = ["unprivileged enable",                         #0
                       "only privileged users enable (until reboot)", #1
                       "only privileged users enabled"]               #2
            print("Checking if kernel.unprivileged_bpf_disabled != 0 for series >= Bionic")
            if self.series == 'trusty':
                print("Skip this test on Trusty as there is no such config.")
            else:
                result = int(utils.system_output('sysctl -n kernel.unprivileged_bpf_disabled'))
                print("unprivileged_bpf_disabled set to: {} - {}".format(result ,meaning[result]))
                if self.series == 'xenial':
                    if result != 0:
                        print("Test Failed, value should be 0 - {} on Xenial".format(meaning[0]))
                        raise error.TestFail()
                elif result != 2:
                    print("Test Failed, value should be 2 - {} >= Bionic".format(meaning[2]))
                    raise error.TestFail()
                print("Test passed.")
            return

        # Enabling unprivileged eBPF to get more tests covered, this will be cleared after reboot (lp:1980756)
        if test_name == 'test_verifier' and self.series not in ['trusty', 'xenial']:
            utils.system('sysctl kernel.unprivileged_bpf_disabled=0')
        os.chdir(os.path.join(self.srcdir, 'linux/tools/testing/selftests/bpf'))
        cmd = './%s' % test_name
        self.results = utils.system_output(cmd, retain_output=True)

# vi:set ts=4 sw=4 expandtab syntax=python:
