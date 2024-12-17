import os
import re
import platform
from autotest.client import test, utils
from autotest.client.shared import error


class ubuntu_boot(test.test):
    version = 1
    def setup(self):
        with open('/etc/os-release', 'r') as fh:
            content = fh.read()
        if 'Ubuntu Core' in content:
            print('Running Ubuntu Core system, skipping apt commands.')
        else:
            pkgs = [ 'python3', 'keyutils' ]
            cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
            self.results = utils.system_output(cmd, retain_output=True)

    def log_check(self):
        '''Test for checking error patterns in log files'''
        '''Centos Specific Boot Test Checks'''
        try:
            os_dist = platform.linux_distribution()[0].split(' ')[0]
        except AttributeError:
            import distro
            os_dist = distro.linux_distribution()[0].split(' ')[0]

        # dmesg will be cleared out in autotest with dmesg -c before the test starts
        # Let's check for /var/log/syslog instead
        if os_dist == 'CentOS':
            logfile = '/var/log/messages'
        else:
            logfile = '/var/log/syslog'
        patterns = [
            'kernel:( \[ *\d+\.\d+\])? BUG:.*',
            'kernel:( \[ *\d+\.\d+\])? Oops:.*',
            'kernel:( \[ *\d+\.\d+\])? kernel BUG at.*',
            'kernel:( \[ *\d+\.\d+\])? WARNING:.*'
        ]
        test_passed = True
        if not os.path.exists(logfile):
            # Hack for systems without syslog (Ubuntu Core)
            logfile = '/tmp/journalctl-syslog'
            utils.system('journalctl -k > {}'.format(logfile))

        if os.path.exists(logfile):
            print('Checking error message in {}:'.format(logfile))
            with open(logfile) as f:
                content = f.read()
                for pat in patterns:
                    print('Scanning for pattern "{}"'.format(pat))
                    if re.search(pat, content):
                        print('Pattern found. Matching lines as follows:')
                        for item in re.finditer(pat, content):
                            print(item.group(0))
                        test_passed = False
                        print('==== Complete syslog ====')
                        print(content)
                    else:
                        print('PASSED, log clean.')
        else:
            print('Log file was not found.')
            test_passed = False
        return test_passed

    def kernel_tainted(self):
        '''Test for checking kernel tatined flags'''
        test_passed = True
        print('Checking kernel tainted flags in /proc/sys/kernel/tainted')
        result = utils.system('python3 %s/kernel_taint_test.py' % self.bindir, ignore_status=True)
        return result

    def kernel_revocation_list(self):
        '''Test for kernel builtin revoked keys'''
        print('Checking kernel revocation list')
        result = utils.system('python3 %s/kernel_revocation_list.py' % self.bindir, ignore_status=True)
        return result

    def run_once(self, test_name, exit_on_error=True):
        if test_name == 'log_check':
            if not self.log_check():
                raise error.TestFail()
            else:
                print("GOOD: Log clean.")
            return
        elif test_name == 'kernel_tainted':
            if self.kernel_tainted():
                raise error.TestFail()
            else:
                print('GOOD: Test Passed.')
            return
        elif test_name == 'kernel_revocation_list':
            if self.kernel_revocation_list():
                raise error.TestFail()
            else:
                print('GOOD: Kernel revocation list.')
            return

        cmd = "uname -a"
        utils.system(cmd)
        cmd = "cat /etc/os-release"
        utils.system(cmd)
