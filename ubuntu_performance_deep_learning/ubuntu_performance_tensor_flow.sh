#!/usr/bin/env bash
#
# perform TensorFlow performance testing and corresponding pre-setup.
#

set -eo pipefail

CONTAINER_VER="23.03"
DISTRIBUTION="$(. /etc/os-release;echo "$ID$VERSION_ID")"

install_nvidia_docker_legacy() {
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L "https://nvidia.github.io/nvidia-docker/$DISTRIBUTION/nvidia-docker.list" | \
        sudo tee /etc/apt/sources.list.d/nvidia-docker.list > /dev/null
    sudo apt update
    sudo apt install nvidia-docker2 -y
    sudo systemctl restart docker
}

install_nvidia_docker_nct() {
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    gpg --dearmor -o - | sudo tee /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && \
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    sudo apt update
    sudo apt install docker.io nvidia-container-toolkit -y
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker
}

install_nvidia_docker() {
    # nvidia-docker is deprecated and not available for Noble,
    # so use the more modern nvidia-container-toolkit.
    if [ "$DISTRIBUTION" = "ubuntu24.04" ]; then
        install_nvidia_docker_nct
    else
        install_nvidia_docker_legacy
    fi
}

get_num_gpus() {
    # required to passthrough GPUs into containers
    nvidia-smi -L | wc -l
}

setup() {
    # pre-setup testing environment and necessary tools
    install_nvidia_docker
}

run_test_legacy() {
    sudo nvidia-docker run \
         --shm-size=1g \
         --ulimit memlock=-1 \
         --ulimit stack=67108864 \
         --rm nvcr.io/nvidia/tensorflow:${CONTAINER_VER}-tf1-py3 -- \
         mpiexec \
         --bind-to socket \
         --allow-run-as-root \
         -np "$(get_num_gpus)" \
         python -u /workspace/nvidia-examples/cnn/resnet.py \
         --layers=50 \
         --precision=fp16 \
         --batch_size=256 \
         --num_iter=300 \
         --iter_unit=batch \
         --display_every=300
}

run_test_nct() {
    sudo docker run \
         --gpus all \
         --shm-size=1g \
         --ulimit memlock=-1 \
         --ulimit stack=67108864 \
         --rm nvcr.io/nvidia/tensorflow:${CONTAINER_VER}-tf1-py3 -- \
         mpiexec \
         --bind-to socket \
         --allow-run-as-root \
         -np "$(get_num_gpus)" \
         python -u /workspace/nvidia-examples/cnn/resnet.py \
         --layers=50 \
         --precision=fp16 \
         --batch_size=256 \
         --num_iter=300 \
         --iter_unit=batch \
         --display_every=300
}

run_test() {
    if [ "$DISTRIBUTION" = "ubuntu24.04" ]; then
        run_test_nct
    else
        run_test_legacy
    fi
}

case $1 in
    setup)
        echo ""
        echo "On setting up necessary test environment..."
        echo ""
        setup
        echo ""
        echo "Setting up necessary test environment..."
        echo ""
        ;;
    test)
        echo ""
        echo "On running test..."
        echo ""
        run_test
        echo ""
        echo "Running test..."
        echo ""
        ;;
esac
