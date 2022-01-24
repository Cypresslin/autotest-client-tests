#!/usr/bin/env bash

set -e
set -x

source ./00-vars

# We want e.g. gds-tools-11-4 if using CUDA 11.4
gds_tools="gds-tools-$(echo "$CUDA_BRANCH" | tr "." "-")"

apt update
apt install "$gds_tools" libssl-dev -y
cd /usr/local/cuda/gds/samples
make -j "$(nproc)"
dd status=none if=/dev/urandom of=/data/file1 iflag=fullblock bs=1M count=1024
dd status=none if=/dev/urandom of=/data/file2 iflag=fullblock bs=1M count=1024

#Edit cufile.json and set "allow_compat" property to "false".
sed -i 's/"allow_compat_mode": true,/"allow_compat_mode": false,/' /etc/cufile.json

echo "sample1"
./cufile_sample_001 /data/file1 0
echo "sample 2"
./cufile_sample_002 /data/file1 0
echo "sample 3"
./cufile_sample_003 /data/file1 /data/file2 0
echo "sample 4"
./cufile_sample_004 /data/file1 /data/file2 0
echo "sample 5"
./cufile_sample_005 /data/file1 /data/file2 0
echo "sample 6"
./cufile_sample_006 /data/file1 /data/file2 0
echo "sample 7"
./cufile_sample_007 0
echo "sample 8"
./cufile_sample_008 0
echo "sample 14"
./cufile_sample_014 /data/file1 /data/file2 0
