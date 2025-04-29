import logging
from autotest.client.test import test
from autotest.client.shared import utils

class rtla_timerlat(test):
    version = 1

    def run_once(self, test_name, args="", exit_on_error=True):
        timeout_s = 60 * 10
        # stdout, maybe also stderr? Unsure.
        output = utils.system_output("{}/timerlat_test --duration {} --verbose".format(self.bindir, timeout_s), retain_output=True)
        lines = output.splitlines()
        influxdb_lines = (line for line in lines if "rtla_timerlat__" in line)
        for line in influxdb_lines:
            logging.info(line)
