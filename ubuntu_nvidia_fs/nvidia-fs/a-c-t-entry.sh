#!/usr/bin/env bash

set -e
set -x

# make sure a-c-t invoke the script in the right directory context
run_test() {
    exe_dir=$(dirname "${BASH_SOURCE[0]}")
    pushd "${exe_dir}"
    ./test-nvidia-fs.sh
    popd
}

run_test
