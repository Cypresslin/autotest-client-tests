#
#
from autotest.client                        import test
from autotest.client.shared                 import error
import re

class nvidia_kernel_config_verification(test.test):
    version = 1

    def initialize(self):
        pass

    def run_once(self, ssid=None, wpapsk='', test_time=10, exit_on_error=True, set_time=True):
        '''
        The kernel configuration settings are stored in /boot/config-<kernel_version>. Create a dictionary of
        the settings and verify they match our expectations.
        '''

        # Get the kernel version from /proc/version_signature
        #
        with open('/proc/version_signature', 'r') as f:
            _, kernel_version, kernel_version_upstream = f.read().strip().split(' ')
            v_rc = re.compile(r'^(\d+\.\d+\.\d+-\d+)\.\d+(-\S+$)')
            match = v_rc.search(kernel_version)
            if match:
                kernel_version = match.group(1) + match.group(2)
            else:
                print('>> match failed <<')

        kconfigs = {}
        with open('/boot/config-' + kernel_version, 'r') as f:
            conf = f.read().split('\n')

            for line in conf:
                line.strip()
                if '=' in line:
                    cfg, val = line.split('=', 1)
                    kconfigs[cfg] = val

        nv_configs = {
            'CONFIG_NR_CPUS'                           : '512',
            'CONFIG_ARM64_64K_PAGES'                   : 'y',
            'CONFIG_NR_CPUS'                           : '512',
            'CONFIG_NODES_SHIFT'                       : '6',
            'CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE'  : 'y',
            'CONFIG_CPU_FREQ_GOV_SCHEDUTIL'            : 'y',
            'CONFIG_PREEMPT_DYNAMIC'                   : 'y',
            'CONFIG_PREEMPT_NONE'                      : 'y',
            'CONFIG_ARM_CORESIGHT_PMU_ARCH_SYSTEM_PMU' : 'm',
            'CONFIG_TCG_TIS_SPI'                       : 'm',
            'CONFIG_MTD_SPI_NOR'                       : 'y',
        }

        passed = True
        for cfg in nv_configs:
            if cfg not in kconfigs:
                print('* %s expected but undefined' % (cfg))
                passed = False
                continue
            if kconfigs[cfg] != nv_configs[cfg]:
                print('* %s expected %s but found %s instead' % (cfg, nv_configs[cfg], kconfigs[cfg]))
                passed = False

        if not passed:
            raise error.TestError('Verification of kernel config options failed.')

# vi:set ts=4 sw=4 expandtab syntax=python:
