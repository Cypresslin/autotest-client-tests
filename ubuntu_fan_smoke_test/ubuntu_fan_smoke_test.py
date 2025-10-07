#
#
import os
import platform
import re
from autotest.client                        import test, utils

class ubuntu_fan_smoke_test(test.test):
    version = 1

    def install_required_pkgs(self):
        arch   = platform.machine()
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()

        pkgs = [
            'docker.io',
            'gdb',
            'git',
            'iproute2',
            'net-tools',
            'ubuntu-fan',
        ]

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def initialize(self):
        pass

    def setup(self):
        self.install_required_pkgs()

    def determine_underlay(self):
        underlay = 'bogus'
        cmd = 'ip address'
        output = utils.system_output(cmd, retain_output=False)
        for line in output.split('\n'):
            m = re.search('inet (\d+\.\d+)\.\d+\.\d+\/\d+ brd \d+\.\d+\.\d+\.\d+ scope', line)
            if m:
                underlay = '%s.0.0/16' % m.group(1)
                break
        return underlay

    def run_once(self, test_name):
        if test_name == 'setup':
            return

        underlay = self.determine_underlay()

        os.chdir(self.bindir)
        cmd = './ubuntu_fan_smoke_test.sh %s' % (underlay)
        self.results = utils.system_output(cmd, retain_output=True)


    def cleanup(self, test_name):
        if test_name in ['setup', 'fan-smoke-test']:
            return
        cmd = 'apt remove -y --purge docker.io'
        utils.system(cmd)

# vi:set ts=4 sw=4 expandtab syntax=python:
