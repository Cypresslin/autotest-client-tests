#!/usr/bin/env bash

run_test() {
    exe_dir=$(dirname "${BASH_SOURCE[0]}")
    pushd "${exe_dir}"
    ./01-run-test.sh
    popd
}

run_test
