import os
from autotest.client import test, utils

p_dir = os.path.dirname(os.path.abspath(__file__))
sh_executable = os.path.join(p_dir, "ubuntu_nvidia_fs.sh")


class ubuntu_nvidia_fs(test.test):
    version = 1

    def initialize(self):
        pass

    def setup(self):
        cmd = "{} setup".format(sh_executable)
        utils.system(cmd)

    def run_nvidia_fs_in_lxc(self):
        #cmd = os.path.join(p_dir, "./nvidia-fs/a-c-t-entry.sh")
        #utils.system(cmd)
        cmd = "{} test".format(sh_executable)
        utils.system(cmd)

    def run_once(self, test_name):
        print("HELLO WORLD")
        if test_name == "nvidia-fs":
            self.run_nvidia_fs_in_lxc()

            print("")
            print("{} has run.".format(test_name))

        print("")

    def postprocess_iteration(self):
        pass
