#!/usr/bin/env bash

set -e
set -x

source ./00-vars

install_nvidia_docker() {
    local distribution
    distribution="$(. /etc/os-release;echo "$ID$VERSION_ID")"
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L "https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list" | \
        sudo tee /etc/apt/sources.list.d/nvidia-docker.list > /dev/null
    sudo apt update
    sudo apt install -y nvidia-docker2 -y
    sudo systemctl restart docker
}

umount /mnt/nvme || true
parted -s /dev/nvme0n1 -- mklabel gpt
parted -s /dev/nvme0n1 -- mkpart primary ext4 0 100%
udevadm settle
mkfs.ext4 -F "/dev/nvme0n1p1"
mkdir -p /mnt/nvme
mount "/dev/nvme0n1p1" /mnt/nvme -o data=ordered

modprobe nvidia-fs

install_nvidia_docker

container="${CUDA_CONTAINER_NAME}:${CUDA_CONTAINER_TAG}"

docker pull "${container}"
docker run --rm --ipc host --name test_gds --gpus device=all \
       --volume /run/udev:/run/udev:ro \
       --volume /sys/kernel/config:/sys/kernel/config/ \
       --volume /dev:/dev:ro \
       --volume /mnt/nvme:/data/:rw \
       --volume /root:/root/:ro \
       --privileged "${container}" \
       bash -c 'cd /root && ./05-inside-docker-run-test.sh'
