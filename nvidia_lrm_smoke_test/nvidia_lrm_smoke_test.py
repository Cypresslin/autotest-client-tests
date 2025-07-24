import os
import re
import json

from autotest.client import test, utils

CUDA_SAMPLES_BASE_DIR = os.path.expanduser("~")
CUDA_SAMPLES_DIR = os.path.expanduser("~/NVIDIA_CUDA-11.5_Samples")

def get_cuda_sample_path(test_name):
    # NOTE: This scheme is different for cuda-samples versions > 11.6
    sample_subdirs = {
        "matrixMulDrv"     : "0_Simple/matrixMulDrv",
        "simpleTextureDrv" : "0_Simple/simpleTextureDrv",
        "vectorAddDrv"     : "0_Simple/vectorAddDrv",
        "deviceQueryDrv"   : "1_Utilities/deviceQueryDrv",
    }
    cuda_sample_subdir = sample_subdirs[test_name]
    return os.path.join(CUDA_SAMPLES_DIR, cuda_sample_subdir)

def get_cuda_version():
    version_data_txt_path = "/usr/local/cuda/version.txt"
    version_data_json_path = "/usr/local/cuda/version.json"
    if os.path.exists(version_data_txt_path):
        with open(version_data_txt_path) as version_data_txt:
            version_data = version_data_txt.readline()
            pattern = "CUDA Version ([0-9.]+)"
            matches = re.search(pattern, version_data)
            version = matches.groups(1)[0]
            return version
    elif os.path.exists(version_data_json_path):
        with open(version_data_json_path) as version_data_json:
            version_data = json.load(version_data_json)
            version = version_data["cuda"]["version"]
            return version
    else:
        return "Unknown"
        
def get_cuda_toolkit_url():
    arch = utils.system_output("arch")
    cuda_toolkit_flavor = 'linux_sbsa' if arch == 'aarch64' else 'linux'
    # 11.5.2 is compatible with all drivers > 450 and still comes packaged with CUDA samples
    cuda_toolkit_url = \
        "https://developer.download.nvidia.com/compute/cuda/11.5.2/local_installers/cuda_11.5.2_495.29.05_{}.run".format(cuda_toolkit_flavor)
    return cuda_toolkit_url

def get_driver_version():
    pattern = r".*Driver Version: ([0-9\.]*).*"
    nvidia_smi = utils.system_output("nvidia-smi")
    matches = re.search(pattern, nvidia_smi)
    driver_version = matches.groups(1)[0]
    return driver_version

def set_gcc_version():
    utils.system("sudo ln -sf /usr/bin/gcc-9 /usr/bin/gcc")
    utils.system("sudo ln -sf /usr/bin/g++-9 /usr/bin/g++")
    return

def install_cuda():
    cuda_toolkit_url = get_cuda_toolkit_url()
    utils.system("wget --quiet --output-document='./cuda.run' {}".format(cuda_toolkit_url))
    utils.system("chmod u+x ./cuda.run")
    utils.system("sudo DEBIAN_FRONTEND=noninteractive ./cuda.run --silent --toolkit --samples --override --samplespath='{}'".format(CUDA_SAMPLES_BASE_DIR))

def install_packages():
    pkgs = [
        'git',
        'make',
        'g++-9'
    ]
    utils.system("sudo DEBIAN_FRONTEND=noninteractive apt-get install -y {}".format(' '.join(pkgs)))

class nvidia_lrm_smoke_test(test.test):
    version = 2

    def initialize(self):
        pass

    def setup(self):
        install_packages()
        install_cuda()
        set_gcc_version()

        print("NVIDIA Driver version: {}".format(get_driver_version()))
        print("CUDA version: {}".format(get_cuda_version()))

        return

    def run_once(self, test_name):
        if test_name == "setup":
            return

        print("Running test: {}".format(test_name))

        cuda_sample_path = get_cuda_sample_path(test_name)
        os.chdir(cuda_sample_path)

        out = utils.system_output("make")
        print("make: {}".format(out))

        out = utils.system_output("./{}".format(test_name))
        print("./{0}: {1}".format(test_name, out))

        return

    def cleanup(self, test_name):
        pass