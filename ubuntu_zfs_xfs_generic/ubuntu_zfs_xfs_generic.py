#
#
import os
import platform
import shutil
from autotest.client                        import test, utils
from autotest.client                        import canonical
from autotest.client.shared                 import error

class ubuntu_zfs_xfs_generic(test.test):
    version = 5

    def install_required_pkgs(self):
        arch = platform.processor()
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()

        pkgs = [
            'acl',
            'attr',
            'autoconf',
            'autopoint',
            'bc',
            'build-essential',
            'debootstrap',
            'gettext',
            'libblkid-dev',
            'libicu-dev',
            'libssl-dev',
            'libtool',
            'patchutils',
            'pkgconf',
            'uuid-dev'
        ]

        if series in ['precise', 'trusty']:
            utils.system_output('add-apt-repository ppa:zfs-native/stable -y', retain_output=True)
            utils.system_output('apt-get update || true', retain_output=True)
            pkgs.append('ubuntu-zfs')
        else:
            pkgs.append('libtool-bin')
            pkgs.append('zfsutils-linux')

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def initialize(self):
        pass

    # if you change setup, be sure to increment version
    #
    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()
        utils.system_output('rm -f /etc/*/S99autotest || true', retain_output=True)

        utils.system_output('useradd fsgqa || true', retain_output=True)
        utils.system_output('grep -q fsgqa /etc/sudoers || echo \"fsgqa    ALL=(ALL)NOPASSWD: ALL\" >> /etc/sudoers', retain_output=True)

        canonical.setup_proxy()

        print("Fetching xfstests..")
        os.chdir(self.srcdir)
        shutil.rmtree('xfstests-bld', ignore_errors=True)
        utils.system('git clone https://github.com/tytso/xfstests-bld')

        os.chdir(os.path.join(self.srcdir, 'xfstests-bld'))
        commit_bld = '8672804daa67855739592070e1732991179c2ba9'
        print("Using head commit for xfstests-bld " + commit_bld)
        utils.system('git reset --hard ' + commit_bld)

        print("Building tests...")
        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'fstests-bld'))
        utils.system('./get-all')
        utils.system('./build-all')

        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'fstests-bld', 'xfstests-dev'))
        tag_xfs = 'v2023.04.09'
        print("Using version " + tag_xfs + " for xfstests-dev")
        utils.system('git reset --hard ' + tag_xfs)
        print("Patching xfstests-dev to add minimal support for ZFS")
        utils.system('patch -p1 < %s/0001-xfstests-add-minimal-support-for-zfs.patch' % self.bindir)

        utils.system('modprobe zfs')

#        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'xfstests-dev'))
#        commit = "82eda8820ddd68dab0bc35199a53a08f58b1d26c"
#        print("Using xfs from known stable commit point " + commit)
#        utils.system('git reset --hard ' + commit)
#        print("Patching xfstests-dev: fix warning with Awk 5.0.1")
#        utils.system('patch -p1 < %s/0006-generic-001-remove-unnecessary-backslash.patch' % self.bindir)
#        print("Running autoreconf --install")
#        utils.system('autoreconf --install')
#
#        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'xfsprogs-dev'))
#        print("Patching xfstests-dev: fix linker issues with modern gcc")
#        utils.system('patch -p1 < %s/0007-Fix-linker-issues-with-clashing-objects.patch' % self.bindir)
#
#        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'fio'))
#        print("Patching fio: fix linker issues with modern gcc")
#        utils.system('patch -p1 < %s/0008-Fix-linker-issues-by-making-tsc_reliable-a-weak-refe.patch' % self.bindir)
#        print("Patch out raw support")
#        utils.system('patch -p1 < %s/382975557e632efb506836bc1709789e615c9094.patch' % self.bindir)


    def run_once(self, test_name):
        #
        #  We need to call setup first to trigger setup() being
        #  invoked, then we can run run_once per test
        #
        if test_name == 'setup':
            return
        if test_name == 'post-test-zfs-cleanup':
            # Make sure there is no ZFS in use by any filesystem
            try:
                utils.system('df -t zfs &> /dev/null') # return 1 if not found
                print("ZFS in use by filesystem, SKIP cleanup")
            except error.CmdError:
                print("Stop / unload / remove ZFS")
                utils.system('systemctl stop zed')
                utils.system('modprobe -r zfs')
                # No need to consider ubuntu-zfs package on P/T as they've been blacklisted
                utils.system('apt-get remove --yes --force-yes zfsutils-linux')
                # Remove .version for the test, in order to trigger setup() again if we want re-test it
                cmd = 'rm {}/.version'.format(self.srcdir)
                utils.system(cmd)
            return

        os.chdir(os.path.join(self.srcdir, 'xfstests-bld', 'fstests-bld', 'xfstests-dev'))
        cmd = '%s/ubuntu_zfs_xfs_generic.sh %s %s' % (self.bindir, test_name, self.srcdir)
        print("Running: " + cmd)
        self.results = utils.system_output(cmd, retain_output=True)

# vi:set ts=4 sw=4 expandtab syntax=python:
