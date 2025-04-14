#!/usr/bin/env bash
#
# Copyright 2021 Canonical Ltd.
# Written by:
#   Dann Frazier <dann.frazier@canonical.com>
#   Taihsiang Ho <taihsiang.ho@canonical.com>

set -e

source nvidia-module-lib

sudo service nvidia-fabricmanager stop || /bin/true

# Example rdepends output:
# $ apt-cache rdepends --installed "linux-image-$(uname -r)"
# linux-image-6.11.0-17-generic
# Reverse Depends:
#   linux-image-generic-hwe-24.04
kernelvariant=$(apt-cache rdepends --installed "linux-image-$(uname -r)" | tail -n +3 |
                    grep linux-image | head -n 1 | sed -e 's/\s\slinux-image//')
platform=$(get_platform_name)

# Some examples like:
# ubuntu@hot-koala:~$ apt-cache search --names-only "^linux-modules-nvidia-[0-9]+-server-$(uname -r)$"
# linux-modules-nvidia-418-server-5.4.0-90-generic - Linux kernel nvidia modules for version 5.4.0-90
# linux-modules-nvidia-450-server-5.4.0-90-generic - Linux kernel nvidia modules for version 5.4.0-90
# linux-modules-nvidia-460-server-5.4.0-90-generic - Linux kernel nvidia modules for version 5.4.0-90
# linux-modules-nvidia-470-server-5.4.0-90-generic - Linux kernel nvidia modules for version 5.4.0-90
for drvpkg in $(apt-cache search --names-only "^linux-modules-nvidia-[0-9]+-server(-open)?-$(uname -r)$" | cut -d' ' -f1); do
    branch="$(echo "$drvpkg" | cut -d- -f4)"
    if [[ "$drvpkg" == *"$branch-server-open"* ]]; then
        variant="-open"
    else
        variant=""
    fi

    # The meta provides nvidia-prebuilt-kernel. We need to install it so the
    # DKMS package isn't installed instead.
    drvpkgmeta=linux-modules-nvidia-$branch-server$variant$kernelvariant

    if ! pkg_compatible_with_platform "$branch" "$variant" "$platform"; then
        echo "INFO: Skipping $drvpkg on $platform" 1>&2
        continue
    else
        echo "INFO: Testing $drvpkg on $platform" 1>&2
    fi
    uninstall_all_nvidia_mod_pkgs
    recursive_remove_module nvidia
    sudo dmesg -c > /dev/null
    sudo apt install -y "$drvpkg" "$drvpkgmeta" "nvidia-driver-$branch-server$variant"
    sudo modprobe nvidia

    if ! sudo dmesg | grep "NVRM: loading NVIDIA UNIX"; then
        echo "ERROR: Failed to detect nvidia driver initialization message in dmesg"
        exit 1
    fi

    # nvidia-smi will return an error code (6) if no GPUs are detected
    if ! nvidia-smi; then
        echo "ERROR: nvidia-smi failed: rc $?"
        exit 1
    fi
done
