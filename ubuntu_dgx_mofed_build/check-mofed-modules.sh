#!/bin/sh

set -e

# We store a list of expected modules for each Ubuntu release/MOFED version
# pair. This scheme currently does not expect modules lists to differ between
# GA and HWE kernels - which is fine for now because we are only testing GA
# kernels.
printf "INFO: Detecting Ubuntu release version..."
release="$(lsb_release -cs)"
printf " %s\n" $release
printf "INFO: Detecting MOFED driver version..."
mofedver="$(dpkg-query --showformat='${Version}' --show mlnx-ofed-kernel-only ||
		dpkg-query --showformat='${Version}' --show doca-ofed)"
printf " %s\n" ${mofedver}
printf "INFO: Detecting Kernel version..."
kernelver="$(uname -r)"
printf " %s\n" ${kernelver}
actual="$(mktemp)"
printf "INFO: Detecting system architecture..."
arch=$(dpkg --print-architecture)
printf " %s\n" "${arch}"

prev_mofedver=$(cd "$(pwd)/expected-mofed-modules" && echo *.lst "$mofedver" | \
                tr ' ' '\n' | sed -E 's/^([0-9\.\-]+)-[a-z].*$/\1/' | \
                uniq | sort -V | sed -n "/$mofedver/q;p" | tail -n 1)

majorkernelver=${kernelver%%-*}
for try_mofedver in "${mofedver}" "${prev_mofedver}"; do
    if [ "${try_mofedver}" = "${prev_mofedver}" ]; then
        echo "WARN: Fallback: Searching for module list of last known DOCA-OFED/MOFED version ${prev_mofedver}"
    fi

    for list in "${try_mofedver}-${release}-${majorkernelver}-${arch}.lst" \
                "${try_mofedver}-${release}-${majorkernelver}.lst" \
                "${try_mofedver}-${release}-${arch}.lst" \
                "${try_mofedver}-${release}.lst"; do
        expected="$(pwd)/expected-mofed-modules/${list}"
        if [ -f "${expected}" ]; then
            break
        fi
        echo "INFO: No expected module list at '${expected}'"
    done
    if [ -f "${expected}" ]; then
        break
    fi
done

if [ ! -f "${expected}" ]; then
    echo "ERROR: No expected modules list available for MOFED $mofedver on $release" 1>&2
    exit 1
fi

echo "INFO: Using expected module list file '${expected}'"

# This test assumes that the only modules installed here are the MOFED ones.
# If other DKMS packages are installed that will throw it off.
echo "INFO: Scanning for available MOFED kernel modules..."
ls /lib/modules/$(uname -r)/updates/dkms | sort > ${actual}

if diff -u ${expected} ${actual}; then
    echo "INFO: Success: Actual module list matches expected module list."
    exit 0
fi

echo "ERROR: Actual modules list does not match expected modules list" 1>&2
exit 1
