#
#
import os
import platform
from autotest.client                        import test, utils
from autotest.client.shared                 import git

class ubuntu_k8s_unit_tests(test.test):
    version = 1

    def install_required_pkgs(self):
        pkgs = [
            'build-essential',
            'golang',
        ]

        if self.series == 'xenial':
            pkgs.append('docker.io')

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        utils.system_output(cmd, retain_output=True)

    def initialize(self):
        try:
            self.series = platform.dist()[2]
        except AttributeError:
            import distro
            self.series = distro.codename()

    # setup
    #
    #    Automatically run when there is no autotest/client/tmp/<test-suite> directory
    #
    def setup(self):
        self.install_required_pkgs()
        cmd = "go version | grep -oP '(\d+\.)+\d+' | tr '.' ' '  | awk {'print $1 * 10000 + $2 * 100 + $3'}"
        go_ver = utils.system_output(cmd, retain_output=True, verbose=False)
        # The following table was constructed based on the minimum golang requirement
        # in kubernetes/hack/lib/golang.sh and actual build test on Xenial
        ver_table = {1: {'golang': '10602', 'branch': 'release-1.3'},  #X - go1.6.2
                     2: {'golang': '11002', 'branch': 'release-1.12'}, #B - go1.10.4
                     3: {'golang': '11304', 'branch': 'release-1.18'}, #F - go1.13.8
                     4: {'golang': '11600', 'branch': 'release-1.22'}, #H - go1.16.2
                     5: {'golang': '11700', 'branch': 'release-1.23'}} #I - go1.17
        br = 'release-1.3'
        for idx in sorted(ver_table):
            if go_ver >= ver_table[idx]['golang']:
                br = ver_table[idx]['branch']
        git.get_repo('https://github.com/kubernetes/kubernetes.git', branch=br, lbranch=None)

    # run_once
    #
    #    Driven by the control file for each individual test.
    #
    def run_once(self, test_name):
        if test_name == 'setup':
            return

        os.chdir('/tmp/kubernetes.git')
        utils.make('clean')
        self.results = utils.make('test')

# vi:set ts=4 sw=4 expandtab syntax=python:
