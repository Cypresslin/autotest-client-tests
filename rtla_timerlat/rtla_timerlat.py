from autotest.client.test import test
from autotest.client.shared import utils

class rtla_timerlat(test):
    version = 1

    def run_once(self, test_name, args="", exit_on_error=True):
        timeout_s = 60 * 10
        utils.system_output("{}/timerlat_test --duration {}".format(self.bindir, timeout_s), retain_output=True)

