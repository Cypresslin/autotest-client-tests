#!/usr/bin/env bash
#
# perform Nvidia driver load testing and corresponding pre-setup.
#

set -eo pipefail

setup() {
    # pre-setup testing environment and necessary tools
    # currently there is nothing practically but will be used possibly in the future.
    echo "begin to pre-setup testing"
    sudo apt update
    sudo apt install -y xmlstarlet jq
    sudo apt install -y docker.io
}

run_test() {
    exe_dir=$(dirname "${BASH_SOURCE[0]}")
    pushd "${exe_dir}"
    #./test-each-nvidia-server-driver.sh
    ./nvidia-fs/a-c-t-entry.sh
    popd
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
