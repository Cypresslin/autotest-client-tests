#!/usr/bin/env bash

#Make sure we have a gds-tools version
if [ $# -eq 0 ]; then
	echo "No gds-tools version provided"
	exit
fi

apt update
apt install "gds-tools-${1}" libssl-dev -y
major="${1%-*}"
minor="${1#*-}"
if [ "$major" -gt 12 ] || { [ "$major" -eq 12 ] && [ "$minor" -gt 4 ]; }; then
    # For gds/CUDA versions > 12.4 samples are not present in cuda/gds dir
    # Use MagnumIO SDK where gds/samples are present
    cd /root/MagnumIO/gds/samples
else
    cd /usr/local/cuda/gds/samples
fi
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
