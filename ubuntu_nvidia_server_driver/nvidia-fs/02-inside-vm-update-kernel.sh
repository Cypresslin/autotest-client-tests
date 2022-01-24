#!/usr/bin/env bash

set -e
set -x

source ./00-vars

export DEBCONF_FRONTEND="noniteractive"
export DEBIAN_PRIORITY="critical"

enable_proposed() {
    local arch
    local release
    local mirror
    local pockets
    arch="$(dpkg --print-architecture)"
    release="$(lsb_release -cs)"
    pockets="restricted main universe multiverse"

    case $arch in
	i386|amd64)
	    mirror="http://archive.ubuntu.com/ubuntu"
	    ;;
	*)
	    mirror="http://ports.ubuntu.com/ubuntu-ports"
	    ;;
    esac

    echo "deb $mirror ${release}-proposed restricted $pockets" | \
	sudo tee "/etc/apt/sources.list.d/${release}-proposed.list" > /dev/null
    echo "deb-src $mirror ${release}-proposed restricted $pockets" | \
	sudo tee -a "/etc/apt/sources.list.d/${release}-proposed.list" > /dev/null
}

enable_proposed
apt update
apt install -y linux-"${KERNEL_FLAVOR}" \
    linux-modules-nvidia-"${NVIDIA_BRANCH}"-"${KERNEL_FLAVOR}" \
    nvidia-kernel-source-"${NVIDIA_BRANCH}" \
    nvidia-utils-"${NVIDIA_BRANCH}"

# Find the latest kernel version that matches our flavor and create "-test"
# symlinks to it since they will sort highest, making it the default
kver=$(linux-version list | grep -- "-${KERNEL_FLAVOR}$" | \
	   linux-version sort --reverse | head -1)
ln -s "vmlinuz-${kver}" /boot/vmlinuz-test
ln -s "initrd.img-${kver}" /boot/initrd.img-test

# Workaround LP: #1849563
echo "GRUB_CMDLINE_LINUX_DEFAULT=\"\$GRUB_CMDLINE_LINUX_DEFAULT pci=nocrs pci=realloc\"" > /etc/default/grub.d/99-nvidia-fs-test.cfg

update-grub
