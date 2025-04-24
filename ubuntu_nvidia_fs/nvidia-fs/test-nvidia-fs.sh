#!/usr/bin/env bash

#Needed for mapping to Nvidia downloads
OS_VERSION=$(lsb_release -rs)

#Number of GPUs to use (Keep it 1)
NUM_GPUS=1

#Specify the driver versions for the corresponding kernel series
find_nvidia_driver_version() {
    if [ "$OS_VERSION" = "24.04" ]; then
        echo "550"
    elif [ "$OS_VERSION" = "22.04" ]; then
        echo "535"
    elif [ "$OS_VERSION" = "20.04" ]; then
        echo "470"
    fi
}

#Nvidia driver version
DRIVER_VER=$(find_nvidia_driver_version)

#Proble nvidia-smi to check the recommended CUDA version
driver_recommended_cuda_version() {
    nvidia-smi -q -u -x --dtd | xmlstarlet sel -t -v "/nvidia_smi_log/cuda_version"
}

#Find the latest cuda container
find_latest_cuda_container_tag_by_branch() {
    local branch="$1" # e.g. 11.4
    local url_api_base="https://registry.hub.docker.com/v2/repositories/nvidia/cuda/tags"
    local search_tag=devel-ubuntu"${OS_VERSION}"
    local url=${url_api_base}"?name="-"${search_tag}"

    # List all of the available nvidia cuda image tags, filter for
    # devel/ubuntu images that match our cuda x.y, and sort numerically
    # to find the newest minor (x.y.z) version.
    #
    # Output is paginated, this loops through each page.
    while [ "$url" != "null" ]; do
        response=$(curl -L -s "$url")
        url=$(jq -r '."next"' <<< "$response")
        jq -r '."results"[]["name"]' <<< "$response"
    done |
        grep -E "^${branch}(\.[0-9]+)*-${search_tag}$" | \
        sort -n | tail -1
}

#Select the nvme drive for the test
find_nvme_drive() {
    PLATFORM="$(sudo dmidecode -s baseboard-product-name | tr '\n' ' ')"
    if [[ "$PLATFORM" == "NVIDIA DGX-2"* ]]; then
        RAID_SERIALS=("18361EA95391" "194925485011" "18361EA954FE" "18301E87831E" # akis
                      "18361EA95541" "18301E87911C" "18301E8781F0" "18361EA95568" # akis
                      )
        RAID_NUM_DEVS=8
    elif [[ "$PLATFORM" == "DGXA100"* ]]; then
        RAID_SERIALS=("S4YPNE0N503910" "S4YPNE0N503317" "S4YPNE0N503316" "S4YPNE0N503897" # cortez
                      "S4YPNE0N400212" "S4YPNE0N400206" "S4YPNE0N400208" "S4YPNE0N400200" # blanka
                      )
        RAID_NUM_DEVS=4
    elif [[ "$PLATFORM" == "DGXH100"* ]]; then
        RAID_SERIALS=("72M0A08WT2N8" "72M0A08VT2N8" "72T0A01TT2N8" "8230A12JT2N8" # hidon
                      "72L0A068T2N8" "72L0A072T2N8" "8210A006T2N8" "72L0A043T2N8" # hidon
                      )
        RAID_NUM_DEVS=8
    else
        # We shouldn't run on this device.
        return
    fi
    
    for nvmepath in /sys/class/nvme/*; do
        nvme=$(basename "$nvmepath")
        # use xargs to trim whitespace
        serial=$(xargs < "$nvmepath/serial")
        if printf "%s\n" "${RAID_SERIALS[@]}" | grep -q -x "$serial"; then
            echo "/dev/${nvme}n1"
            return
        fi
    done

}

#NVME device to use for GDS
NVME_PATH="$(find_nvme_drive)"
#mount path for GDS
MNT_PATH="/mnt/nvme"


#Install NVIDIA driver
function install_nvidia_driver {
	kernelvariant=$(apt-cache rdepends --installed "linux-image-$(uname -r)" | tail -n +3 |
		                    grep linux-image | head -n 1 | sed -e 's/\s\slinux-image//')
	sudo apt install -y "nvidia-driver-${DRIVER_VER}-server" \
		            "linux-modules-nvidia-${DRIVER_VER}-server${kernelvariant}" \
			    "nvidia-fabricmanager-${DRIVER_VER}"
}

#Setup nvme and mount
function setup_nvme {
	sudo umount ${MNT_PATH} || true
	sudo parted -s ${NVME_PATH} -- mklabel gpt
	sudo parted -s ${NVME_PATH} -- mkpart primary ext4 0 100%
	sudo udevadm settle
	sudo mkfs.ext4 -F ${NVME_PATH}"p1"
	sudo mkdir -p ${MNT_PATH}
	sudo mount "${NVME_PATH}p1" ${MNT_PATH} -o data=ordered
}

#Install Nvidia Container Toolkit
function install_nvidia_ctk {
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
&& curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

	sudo apt-get update
	sudo apt-get install -y nvidia-container-toolkit
	
	sudo nvidia-ctk runtime configure --runtime=docker
	sudo systemctl restart docker
}

# Setup Nvidia
function setup_nvidia {
	sudo systemctl start nvidia-fabricmanager
	#make sure GPU is in persistence mode
	sudo nvidia-smi -pm 1
	sudo nvidia-smi -mig 0
}

#Run the nvidia docker gds sample tests
function run_nvidia_docker {
	CONTAINER="${CUDA_CONTAINER_NAME}:${CUDA_CONTAINER_TAG}"
	echo "$CONTAINER"
	sudo docker pull "${CONTAINER}"
	sudo docker run --rm --ipc host --name test_gds --gpus ${NUM_GPUS} \
       		--volume /run/udev:/run/udev:ro \
       		--volume /sys/kernel/config:/sys/kernel/config/ \
       		--volume /dev:/dev:ro \
       		--volume /mnt/nvme:/data/:rw \
       		--volume ${PWD}:/root/:ro \
       		--volume "${PWD}/MagnumIO:/root/MagnumIO:rw" \
       		--privileged "${CONTAINER}" \
       		bash -c "cd /root && ./run_nvidia_docker.sh ${GDS_TOOLS_VER}"
}

#Get MagnumIO repo which has gds/samples folder
function get_magnum_io_repo {
	# gds/samples have been moved from latest GDS tools packages
	# This repo containes the gds/samples so it will be used for 
	# gds-tools version > 12.4. Otherwise the run_nvidia_docker 
	# script will try to look in gds directory for samples folder
	git clone https://github.com/NVIDIA/MagnumIO.git
}


setup_nvme
install_nvidia_driver
setup_nvidia


#CUDA version
CUDA_BRANCH="$(driver_recommended_cuda_version)"

#For CUDA 12.4 there is no container for Noble. 12.5 CUDA container 
#works fine
if [[ "$OS_VERSION" == "24.04" && "$CUDA_BRANCH" == "12.4" ]]; then
    CUDA_BRANCH="12.5"
fi

#gds-tools version, used by container
GDS_TOOLS_VER=$(echo "$CUDA_BRANCH" | tr '.' '-')
#Nvidia container name
CUDA_CONTAINER_NAME="nvcr.io/nvidia/cuda"
#Nvidia container tag
CUDA_CONTAINER_TAG=$(find_latest_cuda_container_tag_by_branch "$CUDA_BRANCH")
echo "CUDA container tag: $CUDA_CONTAINER_TAG"


install_nvidia_ctk
get_magnum_io_repo
run_nvidia_docker

