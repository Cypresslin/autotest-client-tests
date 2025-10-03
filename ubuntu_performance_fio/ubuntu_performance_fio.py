#
#
import os
import platform
import time
import re
import subprocess
import resource
import shutil
from autotest.client        import test, utils
from autotest.client.shared import error

TEST_FILESYSTEM = os.getenv('TEST_FILESYSTEM')
TEST_DRIVE_DEV  = os.getenv('TEST_DRIVE_DEV')
TEST_MNT = '/mnt/autotest-fio'

#
#  Number of test iterations to get min/max/average stats
#
test_iterations = 3

#
# Size of FIO files in MB
#
file_size_mb=32768
#
# Max size of ramfs image (16GB)
#
max_ramdisk_bytes=16 * 1024 * 1024 * 1024

class ubuntu_performance_fio(test.test):
    version = 0
    version = 1
    systemd_services = [
        "smartd.service",
        "iscsid.service",
        "apport.service",
        "cron.service",
        "anacron.timer",
        "apt-daily.timer",
        "apt-daily-upgrade.timer",
        "fstrim.timer",
        "logrotate.timer",
        "motd-news.timer",
        "man-db.timer",
        "multipathd",
        "snapd",
        "unattended-upgrades"
    ]
    systemctl = "systemctl"

    def stop_services(self):
        stopped_services = []
        for service in self.systemd_services:
            cmd = "%s is-active --quiet %s" % (self.systemctl, service)
            result = subprocess.Popen(cmd, shell=True)
            result.communicate()
            if result.returncode == 0:
                cmd = "%s stop %s" % (self.systemctl, service)
                result = subprocess.Popen(cmd, shell=True)
                result.communicate()
                if result.returncode == 0:
                    stopped_services.append(service)
                else:
                    print("WARNING: could not stop %s" % (service))
        return stopped_services

    def start_services(self, services):
        for service in services:
            cmd = "%s start %s" % (self.systemctl, service)
            result = subprocess.Popen(cmd, shell=True)
            result.communicate()
            if result.returncode != 0:
                print("WARNING: could not start %s" % (service))

    def set_rlimit_nofile(self, newres):
        oldres = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, newres)
        return oldres

    def restore_rlimit_nofile(self, res):
        resource.setrlimit(resource.RLIMIT_NOFILE, res)

    def set_cpu_governor(self, mode):
        cmd = "/usr/bin/cpupower frequency-set -g " + mode + " > /dev/null"
        result = subprocess.Popen(cmd, shell=True, stdout=None, stderr=None)
        result.communicate()
        if result.returncode != 0:
            print("WARNING: could not set CPUs to performance mode '%s'" % mode)

    def set_swap_on(self, swap_on):
        cmd = "/sbin/swapon -a" if swap_on else "/sbin/swapoff -a"
        result = subprocess.Popen(cmd, shell=True, stdout=None, stderr=None)
        result.communicate()
        if result.returncode != 0:
            print("WARNING: could not set swap %s" % ("on" if swap_on else "off"))

    def install_required_pkgs(self):
        arch    = platform.processor()
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()
        release = platform.release()

        pkgs = [
            'build-essential',
            'libaio-dev',
            'linux-tools-generic',
            'linux-tools-' + release,
            'pkg-config',
            'xfsprogs',
            'btrfs-progs',
            'jfsutils',
            'zfsutils-linux',
            'zlib1g-dev'
        ]

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    def setup_drive(self):
        if TEST_FILESYSTEM == None or TEST_DRIVE_DEV == None:
            print("No test drive information provided, running on %s" % os.getcwd())
            return True
        for line in open('/proc/mounts').readlines():
            words = line.split()
            if len(words) > 2 and TEST_DRIVE_DEV in words[0]:
                raise error.TestError("Device %s seems to be mounted on %s, aborting" % (TEST_DRIVE_DEV, words[1]))
                return False

        print("Testing on device %s with file system %s\n" % (TEST_DRIVE_DEV, TEST_FILESYSTEM))

        if os.path.exists(TEST_MNT):
            os.rmdir(TEST_MNT)

        os.mkdir(TEST_MNT)
        self.results = utils.system_output('dd if=/dev/zero of=%s bs=1M count=64' % TEST_DRIVE_DEV)
        if TEST_FILESYSTEM == 'ext4':
            cmd = 'mkfs.ext4 -F ' + TEST_DRIVE_DEV
            self.results += utils.system_output(cmd)
            self.results += utils.system_output('mount ' + TEST_DRIVE_DEV + ' ' + TEST_MNT)
        elif TEST_FILESYSTEM == 'xfs':
            cmd = 'mkfs.xfs -f ' + TEST_DRIVE_DEV
            self.results += utils.system_output(cmd)
            self.results += utils.system_output('mount ' + TEST_DRIVE_DEV + ' ' + TEST_MNT)
        elif TEST_FILESYSTEM == 'btrfs':
            cmd = 'mkfs.btrfs -f ' + TEST_DRIVE_DEV
            self.results += utils.system_output(cmd)
            self.results += utils.system_output('mount ' + TEST_DRIVE_DEV + ' ' + TEST_MNT)
        elif TEST_FILESYSTEM == 'jfs':
            cmd = 'mkfs.jfs ' + TEST_DRIVE_DEV
            self.results += utils.system_output(cmd)
            self.results += utils.system_output('mount ' + TEST_DRIVE_DEV + ' ' + TEST_MNT)
        elif TEST_FILESYSTEM == 'zfs':
            cmd = 'zpool create -f fiopool ' + TEST_DRIVE_DEV
            self.results += utils.system_output(cmd)
            cmd = 'zfs create fiopool/test'
            self.results += utils.system_output(cmd)
            cmd = 'zfs set mountpoint=' + TEST_MNT + ' fiopool/test'
            self.results += utils.system_output(cmd)
        else:
            raise error.TestError("Unknown file system TEST_FILESYSTEM=%s, aborting" % TEST_FILESYSTEM)

        return True

    def cleanup_drive(self):
        if TEST_FILESYSTEM == None or TEST_DRIVE_DEV == None:
            return
        self.results = utils.system_output('umount ' + TEST_MNT)
        if os.path.exists(TEST_MNT):
            os.rmdir(TEST_MNT)
        if TEST_FILESYSTEM == 'zfs':
            self.results += utils.system_output('zpool destroy fiopool')
        for i in xrange(60):
            mounted = False
            for line in open('/proc/mounts').readlines():
                words = line.split()
                if len(words) > 2 and TEST_MNT in words[1]:
                    mounted = True
                    break
            if not mounted:
                return
            time.sleep(1.0)

        raise error.TestError("Failed to unmount %s filesystem from %s, aborting" % (TEST_FILESYSTEM, TEST_MNT))

    def initialize(self):
        pass

    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()

        os.chdir(self.srcdir)
        self.results = utils.system_output('tar xvf %s' % os.path.join(self.bindir, 'fio-3.29.tar.gz'), retain_output=True)
        os.chdir(os.path.join(self.srcdir, 'fio-fio-3.29'))
        utils.configure()
        self.results += utils.system_output('make', retain_output=True)


    def get_filesystem_free_mbytes(self):
        fd = os.open(self.bindir, os.O_RDONLY)
        statvfs = os.fstatvfs(fd)
        os.close(fd);
        return statvfs.f_bsize * statvfs.f_bavail / (1024.0 * 1024.0)

    def get_sysinfo(self):
        print('')
        print('date_ctime "' + time.ctime() + '"')
        print('date_ns %-30.0f' % (time.time() * 1000000000))
        print('kernel_version ' + platform.uname()[2])
        print('hostname ' + platform.node())
        print('virtualization ' + utils.system_output('systemd-detect-virt || true'))
        print('cpus_online ' + utils.system_output('getconf _NPROCESSORS_ONLN'))
        print('cpus_total ' + utils.system_output('getconf _NPROCESSORS_CONF'))
        print('page_size ' + utils.system_output('getconf PAGE_SIZE'))
        print('pages_available ' + utils.system_output('getconf _AVPHYS_PAGES'))
        print('pages_total ' + utils.system_output('getconf _PHYS_PAGES'))
        print('free_disk_mb %.2f' % (self.get_filesystem_free_mbytes()))
        print('run_from_path %s' % (os.getcwd()))
        print('')

    def print_stats(self, benchmark, results, fields):
        return

    def fio_clean_files(self, testname):
        #
        #  Remove any fio data files that may be still around
        #
        time.sleep(5)
        cmd = 'rm -f ' + os.path.join(self.srcdir, testname) + '.*.*'
        results = utils.system_output(cmd, retain_output=True)

    def drop_cache(self):
        #
        #  Ensure cache won't affect test by dropping caches
        #  and ensuring data is sync'd
        #
        utils.system('sync')
        f = open("/proc/sys/vm/drop_caches", "w")
        f.write("3")
        f.close()

    def mk_ramdisk(self, ramdisk_bytes, mount_point):
        #print("ramfs device size: %.2f MB" % (float(ramdisk_bytes) / (1024.0 * 1024.0)))
        platform = self.get_platform()
        if platform == 'DGX2':
            cmd = 'mount -t tmpfs -o size=756G,mpol=bind:0 tmpfs %s ' % (mount_point)
        elif platform == 'DGXA100':
            cmd = 'mount -t tmpfs -o size=1000G,mpol=interleave:0-7 tmpfs %s ' % (mount_point)
        elif platform == 'DGXH100':
            cmd = 'mount -t tmpfs -o size=1000G,mpol=bind:0 tmpfs %s ' % (mount_point)
        else:
            cmd = 'mount -t ramfs none %s -o maxsize=%d' % (mount_point, ramdisk_bytes)
        utils.system_output(cmd, retain_output=True)

    def rm_ramdisk(self, mount_point):
        cmd = 'umount %s' % mount_point
        utils.system_output(cmd, retain_output=True)

    def get_platform(self):
        bpn = utils.system_output('dmidecode -s baseboard-product-name | head -1', retain_output=True)
        if bpn == 'NVIDIA DGX-2':
            return 'DGX2'
        elif bpn == 'DGXA100':
            return 'DGXA100'
        elif bpn == 'DGXH100':
            return 'DGXH100'
        else:
            return 'Generic'

    def run_fio(self, testname, ramdisk_bytes, media, iteration):
        kb_scale = {
            "KiB":  1024.0 / 1000.0,
            "KB": 1000.0 / 1000.0,
            "MiB":  1024.0 * 1024.0 / 1000.0,
            "MB": 1000.0 * 1000.0 / 1000.0,
            "GiB":  1024.0 * 1024.0 * 1024.0 / 1000.0,
            "GB": 1000.0 * 1000.0 * 1000.0 / 1000.0,
        }

        usec_scale = {
            "(nsec)": 1.0 / 1000,
            "(usec)": 1.0,
            "(msec)": 1000.0,
            "(sec)" : 1000000.0,
        }

        self.setup_drive()

        #
        #  Edit various fio configs to use dynamic settings
        #  relevant to this test location and test size
        #
        platform = self.get_platform()
        print(platform)
        if platform is not "Generic":
            test_dir = os.path.join('/raid', 'fio-test')
            self.reuse_test_files = True
        else:
            test_dir = os.path.join(self.srcdir, 'fio-test')
            self.reuse_test_files = False
        if not os.path.isdir(test_dir):
            os.mkdir(test_dir)
        if media == 'ramdisk':
            self.mk_ramdisk(ramdisk_bytes, test_dir)

        shutil.copyfile(os.path.join(self.bindir, platform, media, "global-include.fio"), os.path.join(self.srcdir, "global-include.fio"))

        file = testname + ".fio"
        fin = open(os.path.join(self.bindir, platform, media, file), "r")
        fout = open(os.path.join(self.srcdir, file), "w")

        values = {}
        for line in fin:
            if TEST_FILESYSTEM == None or TEST_DRIVE_DEV == None:
                line = line.replace("DIRECTORY", test_dir)
            else:
                line = line.replace("DIRECTORY", TEST_MNT)
            if line.startswith("size="):
                file_size_mb = line.split("size=", 1)[1].rstrip('\n')
            if line.startswith("[") and line.rstrip('\n').endswith("]") and not line.startswith("[global]"):
                values['testname'] = line.rstrip('\n').strip('[]')
            #
            #  zfs and ramdisk can't do O_DIRECT, so skip this
            #
            if media == 'ramdisk' and "direct=1" in line:
                continue
            if TEST_FILESYSTEM == 'zfs' and "direct=1" in line:
                continue
            fout.write(line)
        fin.close()
        fout.close()

        self.drop_cache()
        if not self.reuse_test_files or iteration == 0:
            self.fio_clean_files(testname)

        #if DGXA100 run fstrim
        if platform == 'DGXA100' or platform == 'DGXH100':
            if media == 'dataset':
                print("Run fstrim")
                cmd = "fstrim " + test_dir
                results = utils.system_output(cmd, retain_output=True)

        #
        #  Run fio
        #
        cmd = os.path.join(self.srcdir, 'fio-fio-3.29', 'fio') + " " + os.path.join(self.srcdir, file)
        results = utils.system_output(cmd, retain_output=True)

        if media == 'ramdisk':
            self.rm_ramdisk(test_dir)
        bw = 0.0
        avg = 0.0
        stdev = 0.0

        #
        #  Extract pertinent factoids, bandwidth and latencies
        #
        for l in results.splitlines():
            for s in l.split():
                if s.startswith("BW="):
                    bw_scaled = float(re.findall(r"[-+]?\d*\.*\d+", s)[0])
                    bw_kb = bw_scaled
                    for sc in kb_scale:
                        if sc in s:
                            bw_kb = bw_scaled * kb_scale[sc]
                    if "read: " in l:
                        values['rd_bandwidth_per_sec'] = bw_scaled
                        values['rd_bandwidth_gib_per_sec'] = bw_kb / kb_scale['GiB']
                    if "write: " in l:
                        values['wr_bandwidth_per_sec'] = bw_scaled
                        values['wr_bandwidth_gib_per_sec'] = bw_kb / kb_scale['GiB']

            idx_avg = l.find("avg=")
            idx_stdev = l.find("stdev=")

            if " lat" in l and idx_avg > -1 and idx_stdev > -1:
                avg = float(re.findall("[-+]?\d*\.*\d+", l[idx_avg:])[0])
                stdev = float(re.findall("[-+]?\d*\.*\d+", l[idx_stdev:])[0])
                for sc in usec_scale:
                    if sc in l:
                        avg = avg * usec_scale[sc]


        testname = testname.replace("-","_")

        values['file_size_mb'] = file_size_mb
        values['bandwidth_kb_per_sec'] = bw_kb
        values['latency_usec_average'] = avg
        values['latency_stddev'] = stdev

        if not self.reuse_test_files or iteration == test_iterations - 1:
            self.fio_clean_files(testname)
        self.cleanup_drive()

        return values

    def run_fio_tests(self, testname, media, ramdisk_bytes):
        values = {}
        test_pass = True

        if 'TEST_CONFIG' in os.environ:
            config = '_' + os.environ['TEST_CONFIG']
        else:
            config = ''

        for i in range(test_iterations):
            print("Test %d of %d:" % (i + 1, test_iterations))
            values[i] = self.run_fio(testname, ramdisk_bytes, media, i)
            print("fio_%s%s_%s_file_size_mb[%d] %s" % (media, config, testname, i, values[i]['file_size_mb']))
            if 'rd_bandwidth_per_sec' in values[i] and 'testname' in values[i]:
                print("fio_%s%s_%s,rd_bandwidth_per_sec[%d] %.2f" % (media, config, values[i]['testname'], i, values[i]['rd_bandwidth_per_sec']))
                print("fio_%s%s_%s,rd_bandwidth_gib_per_sec[%d] %.2f" % (media, config, values[i]['testname'], i, values[i]['rd_bandwidth_gib_per_sec']))
            if 'wr_bandwidth_per_sec' in values[i] and 'testname' in values[i]:
                print("fio_%s%s_%s,wr_bandwidth_per_sec[%d] %.2f" % (media, config, values[i]['testname'], i, values[i]['wr_bandwidth_per_sec']))
                print("fio_%s%s_%s,wr_bandwidth_gib_per_sec[%d] %.2f" % (media, config, values[i]['testname'], i, values[i]['wr_bandwidth_gib_per_sec']))
            print("fio_%s%s_%s_bandwidth_kb_per_sec[%d] %.2f" % (media, config, testname, i, values[i]['bandwidth_kb_per_sec']))
            print("fio_%s%s_%s_latency_usec_average[%d] %.2f" % (media, config, testname, i, values[i]['latency_usec_average']))
            print("fio_%s%s_%s_latency_stddev[%d] %.2f" % (media, config, testname, i, values[i]['latency_stddev']))

        #
        #  Compute min/max/average:
        #
        fields = [ 'bandwidth_kb_per_sec', 'latency_usec_average' ]
        print("")
        print("Collated Performance Metrics:")
        for field in fields:
            v = [ float(values[i][field]) for i in values ]
            maximum = max(v)
            minimum = min(v)
            average = sum(v) / float(len(v))
            max_err = (maximum - minimum) / average * 100.0
            str = field.lower().replace("-", "_").replace(",","_")

            print("")
            print("fio_%s%s_%s_%s_minimum %.5f" % (media, config, testname, str, minimum))
            print("fio_%s%s_%s_%s_maximum %.5f" % (media, config, testname, str, maximum))
            print("fio_%s%s_%s_%s_average %.5f" % (media, config, testname, str, average))
            print("fio_%s%s_%s_%s_maximum_error %.2f%%" % (media, config, testname, str, max_err))

            if max_err > 5.0:
                print("FAIL: maximum error is greater than 5%")
                test_pass = False

        print("")
        if test_pass:
            print("PASS: test passes specified performance thresholds")


    def run_once(self, test_name, media):
        if test_name == 'setup':
            self.setup()
            self.get_sysinfo()
            return
        elif test_name == 'post-test-zfs-cleanup':
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

        #
        #  Drop cache to get a good idea of how much free memory can be used
        #
        self.drop_cache()
        page_size = float(utils.system_output('getconf PAGE_SIZE', retain_output=True))
        pages_available = float(utils.system_output('getconf _AVPHYS_PAGES', retain_output=True))
        mem_bytes = page_size * pages_available
        mem_mb = mem_bytes / (1024.0 * 1024.0)
        ramdisk_bytes = mem_bytes / 4
        if ramdisk_bytes > max_ramdisk_bytes:
            ramdisk_bytes = max_ramdisk_bytes

        #if mem_mb > file_size_mb:
        #    print("\nNOTE: file size of %.2f MB should be at least twice the free memory size of %.2f MB when using non-direct I/O" % (file_size_mb, mem_mb))

        free_mb = self.get_filesystem_free_mbytes()
        if free_mb > file_size_mb:
            self.stopped_services = self.stop_services()
            self.oldres = self.set_rlimit_nofile((500000, 500000))
            self.set_cpu_governor('performance')
            self.set_swap_on(False)

            self.run_fio_tests(test_name, media, ramdisk_bytes)

            self.set_swap_on(True)
            self.set_cpu_governor('powersave')
            self.set_rlimit_nofile(self.oldres)
            self.start_services(self.stopped_services)
        else:
            print('cannot execute "%s", required %dMB, only got %dMB on disc' % (test_name, file_size_mb, free_mb))
        print("")

# vi:set ts=4 sw=4 expandtab syntax=python:
