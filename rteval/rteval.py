import multiprocessing
import os
import platform
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from autotest.client import canonical, test, utils
from autotest.client.shared import error

class rteval(test.test):
    version = 1

    def initialize(self):
        self.flavour = re.split('-\d*-', platform.uname()[2])[-1]
        self.arch = platform.processor()
        self.hostname = os.uname()[1]

    def install_required_pkgs(self):
        try:
            series = platform.dist()[2]
        except AttributeError:
            import distro
            series = distro.codename()

        pkgs = [
            'build-essential',
            'git',
            'libnuma-dev',
            'python3-dmidecode',
            'python3-lxml',
            'python3-ethtool',
            'python3-requests',
            'flex',
            'bison',
            'libelf-dev',
            'libncurses-dev',
            'gawk', 
            'openssl',
            'libssl-dev',
            'dkms',
            'libudev-dev',
            'libpci-dev',
            'libiberty-dev',
            'autoconf',
            'llvm',
            'rt-tests'
        ]
        gcc = 'gcc' if self.arch in ['ppc64le', 'aarch64', 's390x', 'riscv64'] else 'gcc-multilib'
        pkgs.append(gcc)

        cmd = 'yes "" | DEBIAN_FRONTEND=noninteractive apt-get install --yes --force-yes ' + ' '.join(pkgs)
        self.results = utils.system_output(cmd, retain_output=True)

    # setup
    #
    #    Automatically run when there is no autotest/client/tmp/<test-suite> directory
    #
    def setup(self):
        self.install_required_pkgs()
        self.job.require_gcc()
        os.chdir(self.srcdir)
        shutil.rmtree('rteval', ignore_errors=True)
        canonical.setup_proxy()
        branch = 'main'
        cmd = 'git clone -b {} https://git.kernel.org/pub/scm/utils/rteval/rteval.git'.format(branch)
        utils.system_output(cmd, retain_output=True)

        # Print test suite HEAD SHA1 commit id for future reference
        os.chdir(os.path.join(self.srcdir, 'rteval'))
        title_local = utils.system_output("git log --oneline -1 | sed 's/(.*)//'", retain_output=False, verbose=False)
        title_upstream = utils.system_output("git log --oneline | grep -v SAUCE | head -1", retain_output=False, verbose=False)
        print("Latest commit in '{}' branch: {}".format(branch, title_local))
        print("Latest upstream commit: {}".format(title_upstream))
        os.mkdir("install")

        # Download Linux tarball referenced in the Makefile
        with open("Makefile", mode="rt") as makefile:
            makefile_content = makefile.read()
            linux_version_match = re.search(r'KLOAD\s*:=\s*\$\(LOADDIR\)\/(linux-\d+\.\d+(\.\d+)?(-rc\d+)?\.tar\.[gx]z)', makefile_content)
            if linux_version_match:
                linux_version = linux_version_match.group(1)
                print("Linux version download used in testing:", linux_version)
                if "rc" in linux_version: # RCs in a different location on kernel.org
                    cmd = 'wget -nv -P loadsource https://git.kernel.org/torvalds/t/'+linux_version
                else:
                    cmd = 'wget -nv -P loadsource https://cdn.kernel.org/pub/linux/kernel/v'+linux_version.split('-')[1].split('.')[0]+'.x/'+linux_version
                    
                utils.system_output(cmd, retain_output=True)
            else:
                print("Linux version download for testing not found.")

        # Build test
        try:
            nprocs = 'install -j' + str(multiprocessing.cpu_count())
        except:
            nprocs = 'install'
        utils.make(nprocs)

        # Copy in config file
        shutil.copy2( self.bindir+"/rteval.conf", self.srcdir+"/rteval/" )


    # run_once
    #
    #    Driven by the control file for each individual test.
    #
    #    Runs rteval. Test passes if max latency is not over specified limit.
    #
    def run_once(self, test_name, args='', exit_on_error=True):
        if test_name == 'setup':
            return

        # Run rteval
        os.chdir(self.srcdir+"/rteval")
        utils.make('runit')

        # Find the summary XML results
        results_count = 0
        subfolders = [f for f in os.listdir(self.srcdir+"/rteval/run/") if os.path.isdir(os.path.join(self.srcdir+"/rteval/run/", f))]
        for folder in subfolders:
            folder_match = re.search(r"rteval-"+datetime.now().strftime('%Y%m%d')+"-(\d)+[^(.tar.bz2)]?", folder)
            if folder_match:
                results_count += 1

        if 0 == results_count:
            raise error.TestError('FAIL: rteval results not found.')

        xml_path = self.srcdir+"/rteval/run/rteval-"+datetime.now().strftime('%Y%m%d')+"-"+str(results_count)+"/summary.xml"

        # Parse the XML results and find the first "maximum" tag, which gives 
        # max system latency
        with open(xml_path, 'r') as results_file:
            results_string = results_file.read()

        xml_root = ET.fromstring(results_string)
        maximum_tag = xml_root.find(".//maximum")
        mean_tag = xml_root.find(".//mean")
        minimum_tag = xml_root.find(".//minimum")

        if maximum_tag is None:
            raise error.TestError('FAIL: Max latency not found.')

        if mean_tag is None:
            raise error.TestError('FAIL: Mean latency not found.')

        if minimum_tag is None:
            raise error.TestError('FAIL: Minimum latency not found.')

        max_latency = maximum_tag.text
        mean_latency = mean_tag.text
        minimum_latency = minimum_tag.text

        # Print stats in format used by mass-scrape-influxdb.sh
        print("rteval_latency_maximum %.3f" % float(max_latency))
        print("rteval_latency_average %.3f" % float(mean_latency))
        print("rteval_latency_minimum %.3f" % float(minimum_latency))

        latency_limit = 700
        if self.hostname in ['starlow', 'drapion']:
            latency_limit = 150
        elif self.hostname in ['taycet', 'bunsen']:
            latency_limit = 300

        # Only fail real-time kernels on high latency
        if int(max_latency) > latency_limit and "realtime" in self.flavour:
            raise error.TestError('FAIL: Max latency over ' + str(latency_limit) + 'us.')

        return
