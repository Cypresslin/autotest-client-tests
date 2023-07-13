#!/usr/bin/env bash
#
# Exercising the NVIDIA GPU Direct RDMA performance testing on Ubuntu
#

set -eo pipefail

setup() {
    # pre-setup testing environment and necessary tools
    # currently there is nothing practically but will be used possibly in the future.
    echo "begin to pre-setup testing"
}

run_test() {
    exe_dir=$(dirname "${BASH_SOURCE[0]}")
    pushd "${exe_dir}"/nvidia-peermem-test/
    ./nvidia-peermem-test.sh
    popd
}

case $1 in
    setup)
        echo ""
        echo "[GPUDirect RDMA] On setting up necessary test environment..."
        echo ""
        setup
        echo ""
        echo "[GPUDirect RDMA] Set up necessary test environment."
        echo ""
        ;;
    test_ib_peer_memory)
        echo ""
        echo "[GPUDirect RDMA] On running test_ib_peer_memory..."
        echo ""
        run_test
        echo ""
        echo "[GPUDirect RDMA] Run test_ib_peer_memory."
        echo ""
        ;;
esac
