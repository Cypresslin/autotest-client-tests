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

# First check for a list specific to this major kernel version
expected="$(pwd)/expected-mofed-modules/${mofedver}-${release}-${kernelver%%-*}.lst"
if [ ! -f "${expected}" ]; then
	# Fall back to a general list for this MOFED version & series combination.
	printf "INFO: No expected module list at '%s', falling back to " "${expected}"
	expected="$(pwd)/expected-mofed-modules/${mofedver}-${release}.lst"
	printf "'%s'\n" "${expected}"
fi

# This test assumes that the only modules installed here are the MOFED ones.
# If other DKMS packages are installed that will throw it off.
echo "INFO: Scanning for available MOFED kernel modules..."
ls /lib/modules/$(uname -r)/updates/dkms | sort > ${actual}

if [ ! -f ${expected} ]; then
    echo "ERROR: No expected modules list available for MOFED $mofedver on $release" 1>&2
    exit 1
fi

echo "INFO: Using expected module list file '${expected}'"

if diff -u ${expected} ${actual}; then
    echo "INFO: Success: Actual module list matches expected module list."
    exit 0
fi

echo "ERROR: Actual modules list does not match expected modules list" 1>&2
exit 1
