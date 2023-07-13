import os
from autotest.client import test, utils

p_dir = os.path.dirname(os.path.abspath(__file__))
sh_executable = os.path.join(p_dir, "ubuntu_performance_gpudirect_rdma.sh")


class ubuntu_performance_gpudirect_rdma(test.test):
    version = 1

    def initialize(self):
        pass

    def setup(self):
        cmd = "{} setup".format(sh_executable)
        utils.system(cmd)

    def run_ib_peer_memory(self):
        cmd = "{} test_ib_peer_memory".format(sh_executable)
        utils.system(cmd)

    def run_once(self, test_name):
        if test_name == "ib_peer_memory":
            self.run_ib_peer_memory()

            print("")
            print("{} has run.".format(test_name))

        print("")

    def postprocess_iteration(self):
        pass
