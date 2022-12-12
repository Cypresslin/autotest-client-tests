#
#
import platform
from autotest.client                        import test, utils
from autotest.client.shared                 import error

class ubuntu_sysdig_smoke_test(test.test):
    version = 99

    def install_required_pkgs(self):
        pkgs = [
            'sysdig'
        ]
        pkgs.append(self.dkms_pkg)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True, ignore_status=True)

    def initialize(self):
        try:
            self.series = platform.dist()[2]
        except AttributeError:
            import distro
            self.series = distro.codename()

        dkms = 'scap'
        self.dkms_pkg = 'falcosecurity-scap-dkms'
        self.cleanup_target = 'scap'
        log_path = '/var/lib/dkms/{}/kernel-*/log/make.log'.format(dkms)
        if self.series in ['xenial', 'bionic', 'focal', 'jammy']:
            dkms = 'sysdig'
            self.dkms_pkg = 'sysdig-dkms'
            self.cleanup_target = 'sysdig_probe'
            log_path = '/var/lib/dkms/{}/*/build/make.log'.format(dkms)
        self.install_required_pkgs()
        cmd = 'dkms status -m {} | grep installed'.format(dkms)
        try:
            utils.system(cmd)
        except error.CmdError:
            cmd = 'cat {}'.format(log_path)
            utils.system(cmd)
            raise error.TestError('DKMS failed to install')

    def run_once(self, test_name):
        cmd = '%s/ubuntu_sysdig_smoke_test.sh' % (self.bindir)
        self.results = utils.system_output(cmd, retain_output=True)
        print(self.results)

    def cleanup(self):
        cmd = 'modprobe -r {} || true'.format(self.cleanup_target)
        self.results = utils.system_output(cmd, retain_output=False)
        cmd = 'apt-get remove --purge {} -y'.format(self.dkms_pkg)
        self.results = utils.system_output(cmd, retain_output=False)


# vi:set ts=4 sw=4 expandtab syntax=python:
