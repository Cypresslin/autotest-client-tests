#!/usr/bin/env bash

set -e
set -x
set -o pipefail

shopt -s nullglob

rm -f 00-vars.gen # avoid stale configs from previous runs
source 00-vars
source ../nvidia-module-lib

sudo apt install -y jq xmlstarlet

driver_recommended_cuda_version() {
    local xmlout
    xmlout="$(mktemp)"

    sudo nvidia-smi -q -u -x --dtd | tee "$xmlout" > /dev/null
    xmlstarlet sel -t -v "/nvidia_smi_log/cuda_version" < "$xmlout"
    rm -f "$xmlout"
}

find_latest_cuda_container_tag_by_branch() {
    local branch="$1" # e.g. 11.4
    local tmpfile="$(mktemp)"
    local url_api_base="https://registry.hub.docker.com/v2/repositories/nvidia/cuda/tags"
    source ./00-vars.gen # pick up LXD_OS_VER
    local search_tag=devel-ubuntu"${LXD_OS_VER}"
    local url=${url_api_base}"?name="-"${search_tag}"

    # List all of the available nvidia cuda image tags, filter for
    # devel/ubuntu images that match our cuda x.y, and sort numerically
    # to find the newest minor (x.y.z) version.
    #
    # Output is paginated, this loops through each page.
    while [ "$url" != "null" ]; do
        curl -L -s "$url" > "$tmpfile"
        url="$(jq '."next"' < "$tmpfile" | tr -d \")"
        jq '."results"[]["name"]' < "$tmpfile" |
            tr -d \"
    done |
        grep -E "^${branch}(\.[0-9]+)*-${search_tag}$" | \
        sort -n | tail -1
    rm -f "$tmpfile"
}

gen_vars() {
    local cuda_branch
    local container_tag

    # Match the host OS
    echo "LXD_OS_CODENAME=$(lsb_release -cs)" > 00-vars.gen
    echo "LXD_OS_VER=$(lsb_release -rs)" >> 00-vars.gen
    cuda_branch="$(driver_recommended_cuda_version)"
    container_tag="$(find_latest_cuda_container_tag_by_branch "$cuda_branch")"
    echo "CUDA_BRANCH=${cuda_branch}" >> 00-vars.gen
    echo "CUDA_CONTAINER_TAG=${container_tag}" >> 00-vars.gen
}

lxd_wait() {
    local instance="$1"

    for _ in $(seq 300); do
        if lxc exec "${instance}" -- /bin/true; then
	    break
	fi
	sleep 1
    done
}

is_whole_nvme_dev() {
    local dev
    dev="$(basename "$1")"
    echo "$dev" | grep -Eq '^nvme[0-9]+n[0-9]+$'
}

find_free_nvme() {
    local dev
    local children
    command -v jq > /dev/null || sudo apt install -y jq 1>&2
    for dev in /dev/nvme*; do
	is_whole_nvme_dev "$dev" || continue
	# Is this device used by another kernel device (RAID/LVM/etc)?
	children=$(lsblk -J "$dev" | jq '.["blockdevices"][0]."children"')
	if [ "$children" = "null" ]; then
	   echo "$dev"
	   return 0
	fi
    done
    return 1
}

nvme_dev_to_bdf() {
    local dev="$1"
    local bdf=""

    while read -r comp; do
        if echo "$comp" | grep -q -E '^[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]$'; then
            bdf="$comp"
        fi
    done <<<"$(readlink /sys/block/"$(basename "$dev")" | tr / '\n')"
    if [ -z "$bdf" ]; then
        echo "ERROR: name_dev_to_bdf: No PCI address found for $dev" 1>&2
        return 1
    fi
    echo "$bdf"
    return 0
}

gen_vars
source ./00-vars.gen

# 20.04 installs currently get LXD 4.0.7 by default, but we need at least
# 4.11 for PCI passthrough support for VMs. latest/stable is new enough.
sudo snap refresh lxd --channel=latest/stable
sudo lxd init --auto
lxc delete --force "$LXD_INSTANCE" || :

# FIXME: Should probably dynamically adapt cpu/memory based on host system
lxc launch --vm "ubuntu:${LXD_OS_CODENAME}" "$LXD_INSTANCE" \
    -t c48-m16 \
    -c security.secureboot=false # so we can load untrusted modules

# Ran out of space pulling the docker image w/ the default 10GB. Double it.
lxc config device override "${LXD_INSTANCE}" root size=20GB
lxd_wait "${LXD_INSTANCE}"

for file in 00-vars 00-vars.gen 02-inside-vm-update-kernel.sh 03-inside-vm-install-drivers.sh 04-inside-vm-setup-docker-and-run-test.sh 05-inside-docker-run-test.sh; do
    lxc file push ${file} "${LXD_INSTANCE}"/root/${file}
done
lxc exec "${LXD_INSTANCE}" -- /root/02-inside-vm-update-kernel.sh

# Reboot to switch to updated kernel, so new drivers will build for it
lxc stop "${LXD_INSTANCE}"

# Release GPU devices so we can assign them to a VM
sudo service nvidia-fabricmanager stop || :
recursive_remove_module nvidia

## Pass in devices. Note: devices can be assigned only while VM is stopped

# Any Nvidia GPU will do, just grab the first one we find
gpuaddr="$(lspci | grep '3D controller: NVIDIA Corporation' | cut -d' ' -f1 | head -1)"
lxc config device add "${LXD_INSTANCE}" gpu pci "address=${gpuaddr}"

# Find an unused NVMe device to pass in
nvmedev=$(find_free_nvme) || \
    (echo "ERROR: No unused nvme device found" 1>&2 && exit 1)
nvmeaddr="$(nvme_dev_to_bdf "$nvmedev")" || \
    (echo "ERROR: No PCI device found for $nvmedev" 1>&2 && exit 1)
lxc config device add "${LXD_INSTANCE}" nvme pci "address=${nvmeaddr}"

lxc start "${LXD_INSTANCE}"
lxd_wait "${LXD_INSTANCE}"
lxc exec "${LXD_INSTANCE}" -- /root/03-inside-vm-install-drivers.sh

# Reboot to switch to new overridden drivers
lxc stop "${LXD_INSTANCE}"
lxc start "${LXD_INSTANCE}"

lxd_wait "${LXD_INSTANCE}"
lxc exec "${LXD_INSTANCE}" -- /root/04-inside-vm-setup-docker-and-run-test.sh
