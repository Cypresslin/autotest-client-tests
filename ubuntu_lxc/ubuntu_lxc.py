#
#
from autotest.client                        import test, utils
import multiprocessing
import os
import platform
import shutil

class ubuntu_lxc(test.test):
    version = 1

    def install_required_pkgs(self):
        arch  = platform.machine()
        if self.series in ['precise', 'trusty', 'xenial', 'artful']:
            pkgs = [
                'lxc-tests'
            ]
        else:
            pkgs = [
                'autoconf',
                'build-essential',
                'dirmngr',
                'libapparmor-dev',
                'libcap-dev',
                'libtool',
                'lxc',
                'pkg-config',
                'python3-lxc',
            ]
        # For Mantic and newer
        if self.series not in ['precise', 'trusty', 'xenial', 'bionic', 'focal', 'jammy']:
            pkgs.append('meson')
            pkgs.append('docbook2x')
            pkgs.append('docbook-utils')
            pkgs.append('libdbus-1-dev') # LP: #2083805
            pkgs.append('systemd-dev') # LP: #2089812

        pkgs.append('liblxc1')
        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        utils.system_output(cmd, retain_output=True)

    def initialize(self, test_name):
        try:
            self.series = platform.dist()[2]
        except AttributeError:
            import distro
            self.series = distro.codename()

        if test_name != 'setup':
            return

        self.install_required_pkgs()
        if self.series not in ['precise', 'trusty', 'xenial']:
            os.chdir('/tmp')
            shutil.rmtree('lxc-pkg-ubuntu', ignore_errors=True)
            # Fetch source code from the archive instead of https://github.com/lxc/lxc-pkg-ubuntu.git
            # To avoid version mismatch issue LP: #1960094
            utils.system('apt-get source --download-only lxc')
            utils.system("dpkg-source -x lxc*dsc lxc-pkg-ubuntu")
            os.chdir('/tmp/lxc-pkg-ubuntu')
            # For > Xenial and <= Jammy
            if self.series in ['bionic', 'focal', 'jammy']:
                gcc_multiarch = utils.system_output('gcc -print-multiarch',  retain_output=False)
                utils.system('autoreconf -f -i')
                cmd = '--enable-tests --disable-rpath --disable-doc --with-distro=ubuntu \
                       --prefix=/usr --sysconfdir=/etc --localstatedir=/var \
                       --libdir=\${{prefix}}/lib/{0} \
                       --libexecdir=\${{prefix}}/lib/{0} \
                        --with-rootfs-path=\${{prefix}}/lib/{0}/lxc'.format(gcc_multiarch)
                utils.configure(cmd)
            try:
                nprocs = '-j' + str(multiprocessing.cpu_count())
            except:
                nprocs = ''
            utils.make(nprocs)

        # Override the GPG server
        fn = '/usr/share/lxc/templates/lxc-download'
        cmd = "grep -q 'DOWNLOAD_KEYSERVER=\"hkp://keyserver.ubuntu.com:80\"' {0} || sed -i '/^DOWNLOAD_URL=$/a DOWNLOAD_KEYSERVER=\"hkp://keyserver.ubuntu.com:80\"' {0}".format(fn)
        utils.system(cmd)

        # Workaround for broken gpg2
        if os.environ.get('http_proxy') and os.path.isfile('/usr/bin/dirmngr'):
            cmd = 'dpkg-divert --divert /usr/bin/dirmngr.orig --rename --add /usr/bin/dirmngr'
            utils.system(cmd)
            with open('/usr/bin/dirmngr', 'w') as f:
                f.write('#!/bin/sh\n')
                f.write('exec /usr/bin/dirmngr.orig --honor-http-proxy $@\n')
            cmd = 'chmod +x /usr/bin/dirmngr'
            utils.system(cmd)


    def run_once(self, test_name):
        if test_name == 'setup':
            return

        if self.series in ['precise', 'trusty', 'xenial']:
            fpath = '/usr/bin/'
        else:
            fpath = '/tmp/lxc-pkg-ubuntu/src/tests/'

        # Override the path for Python3 API test
        if test_name == 'api_test.py':
            fpath = 'python3 /usr/share/doc/python3-lxc/examples/'

        cmd = fpath + test_name
        utils.system_output(cmd, retain_output=True)

    def cleanup(self, test_name):
        if test_name == 'setup':
            return

        # Make sure to properly cleanup containers that may still exist if
        # sub-tests are failing (LP: #1788574, LP: #1941063)
        leftover_containers = {'lxc-test-api-reboot': 'reboot',
                'lxc-test-device-add-remove': 'device_add_remove_test',
                'lxc-test-mount-injection': 'mount_injection_test',}
        if test_name in leftover_containers:
            print("Stopping and destroying {0}".format(leftover_containers[test_name]))
            cmd = "lxc-destroy -f -n {0} 2>/dev/null || true".format(leftover_containers[test_name])
            utils.system(cmd)

# vi:set ts=4 sw=4 expandtab syntax=python:
