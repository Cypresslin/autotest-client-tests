#!/usr/bin/env bash

set -e
set -x

source ./00-vars

export DEBCONF_FRONTEND="noniteractive"
export DEBIAN_PRIORITY="critical"

# Remove headers for all kernels except the one running so DKMS does not
# try to build modules against them. Other kernels may not be compatible
# with our modules, and we don't want the install to fail because of that.
# We need to do this twice because apt will avoid removing a metapackage
# (e.g. linux-kvm) if it can instead upgrade it, which may pull in a new
# headers package. If that happens, the 2nd time through we'll remove that
# updated headers package as well as the metapackage(s) that brung it.
for _ in 1 2; do
    for file in /lib/modules/*/build; do
	if [ "$file" = "/lib/modules/$(uname -r)/build" ]; then
	    continue
	fi
	apt remove --purge "$(dpkg -S "$file" | cut -d":" -f1 | sed 's/, / /g')" -y
    done
done

# Install MOFED stack
wget -qO - https://www.mellanox.com/downloads/ofed/RPM-GPG-KEY-Mellanox | \
    apt-key add -
wget -qO - "${MLNX_REPO}/${MLNX_OFED_VER}/ubuntu${LXD_OS_VER}/mellanox_mlnx_ofed.list" | tee /etc/apt/sources.list.d/mellanox_mlnx_ofed.list
apt update
apt install -y mlnx-ofed-all mlnx-nvme-dkms mlnx-nfsrdma-dkms

# Install nvidia-fs module
cuda_os="ubuntu$(echo "$LXD_OS_VER" | tr -d .)"
apt-key adv --fetch-keys "https://developer.download.nvidia.com/compute/cuda/repos/${cuda_os}/x86_64/7fa2af80.pub"
add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/${cuda_os}/x86_64/ /"
apt install -y nvidia-fs-dkms
add-apt-repository -r "deb https://developer.download.nvidia.com/compute/cuda/repos/${cuda_os}/x86_64/ /"
