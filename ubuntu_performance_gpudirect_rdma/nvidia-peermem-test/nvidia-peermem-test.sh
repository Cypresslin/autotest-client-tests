#!/bin/bash
#
# This is a smoke test for the kernel IB PeerDirect feature, intended
# for monitoring Ubuntu kernel updates for regressions. We
# don't have a unit test for just that feature, so we instead do a
# smoke test of Nvidia's GPUDirect feature, which uses IB PeerDirect
# underneath. This requires using the Nvidia driver stack.
#
# To avoid orchestrating multiple machines, we instead place 2 IB
# devices on the same machine in separate namespaces. Running the
# client and server in separate namespaces ensures that the traffic
# actually flows over the IB cable between the interfaces.
# We use ib_write_bw from the perftest package to do essentially a
# ping test. perftest from the archive is not configured to build against
# the (non-free) CUDA stack, so we must first rebuild it. This rebuild
# is done in a pbuilder chroot to avoid issues w/ build-dependencies
# installing CUDA versions that don't match the nvidia driver.
#
# Prerequisites:
#   - nvidia-driver-<branch> package installed; nvidia driver loaded
#   - nvidia-fabricmanager, if required, installed and started
#   - 2 local IB ports connected back-to-back
#
# Author: dann frazier <dann.frazier@canonical.com>
#
set -e
set -x

export DEBCONF_FRONTEND="noninteractive"
export DEBIAN_PRIORITY="critical"

hostcfg="hosts.d/$HOSTNAME"
if [ -e "$hostcfg" ]; then
    source "$hostcfg"
else
    echo "ERROR: No configuration file found for $HOSTNAME" 1>&2
    exit 1
fi

sudo_apt() {
    sudo --preserve-env=DEBCONF_FRONTEND,DEBIAN_PRIORITY apt "$@"
}

cleanup() {
    { [ -n "$srvpid" ] && test -d "/proc/$srvpid"; } || \
	sudo kill "$srvpid" || /bin/true
    [ -z "$tmpdir" ] || rm -rf "$tmpdir"
    sudo ip addr del dev "$SERVER_IFACE" "$SERVER_IP" || /bin/true
    sudo ip netns exec peermemclient \
	 ip addr del dev "$CLIENT_IFACE" "$CLIENT_IP" || /bin/true
    sudo ip netns delete peermemclient || /bin/true
}
trap cleanup EXIT

ubuntu_mirror() {
    local arch
    arch="$(dpkg --print-architecture)"
    case $arch in
	amd64|i386)
	    echo "http://archive.ubuntu.com/ubuntu"
	    return
	    ;;
	*)
	    echo "http://ports.ubuntu.com/ubuntu-ports"
	    return
	    ;;
    esac
}

install_cuda_perftest() {
    local release
    local components
    if dpkg-query -W -f '${Version}' perftest | grep -q \+cuda\.1$; then
	# Looks like it is already build and installed
	return
    fi
    release=$(lsb_release -cs)
    components="main universe restricted multiverse"
    # Rebuild perftest w/ CUDA support
    sudo sed -i 's/# deb-src/deb-src/' /etc/apt/sources.list
    sudo_apt update
    sudo_apt build-dep -y perftest
    sudo_apt install -y devscripts fakeroot pbuilder
    tmpdir="$(mktemp -d)"
    pushd "$tmpdir"
    apt source perftest
    pushd perftest-*
    # There's a libnvidia-compute-<branch> package for every driver
    # branch - each one provides a libcuda.1. dpkg-shlibdeps will
    # generate a dependency for which package is installed at build-time.
    # That will end up being whatever branch nvidia-cuda-dev was built for
    # - and that may not match the driver version currently loaded. Using
    # a mismatched libnvidia-compute/driver combo will cause ib_write_bw to
    # error out (803 = cudaErrorSystemDriverMismatch). Override this
    # dependency with the libnvidia-compute virtual package. We'll let
    # apt figure out the best libnvidia-compute-<branch> package to
    # install - it tends to pick the one that matches the installed driver.
    echo "libcuda 1 libnvidia-compute" >> debian/shlibs.local
    ver="$(dpkg-parsechangelog | grep ^Version: | cut -d' ' -f2)+cuda.1"
    DEBFULLNAME="Canonical Kernel Team" \
	       DEBEMAIL="canonical-kernel-team@lists.canonical.com" \
	       dch -v "$ver" "Rebuild with CUDA support"
    dpkg-buildpackage -rfakeroot -uc -us -S
    popd
    # We build in a pbuilder chroot instead of on the host because
    # nvidia-cuda-dev depends may pull in nvidia package versions
    # from branches that mismatch with the host driver branch
    if [ ! -f "/var/cache/pbuilder/${release}.tgz" ]; then
	sudo pbuilder create --distribution "$release" \
	     --mirror "$(ubuntu_mirror)" \
	     --components "$components" \
	     --othermirror "deb $(ubuntu_mirror) ${release}-updates $components" \
	     --basetgz "/var/cache/pbuilder/${release}.tgz"
    fi
    mkdir result
    sudo sed -i 's/^export CUDA_H_PATH=.*//' /etc/pbuilderrc
    echo "export CUDA_H_PATH=/usr/include/cuda.h" | sudo tee -a /etc/pbuilderrc
    sudo pbuilder build --basetgz "/var/cache/pbuilder/${release}.tgz" \
	 --extrapackages nvidia-cuda-dev \
	 --buildresult result perftest_*cuda.1.dsc
    sudo dpkg -i result/perftest_*cuda.1_*.deb || sudo_apt -f install -y
    popd
}

use_cuda_needs_devid() {
    if ib_write_bw --help | grep use_cuda=; then
	return 0
    fi
    return 1
}

# Avoid dpkg lock contention
sudo service unattended-upgrades stop || true

install_cuda_perftest

for ibdev in /sys/class/infiniband/*; do
    # is this lisp?
    bdf="$(basename "$(dirname "$(dirname "$(readlink "$ibdev")")")")"
    case "$bdf" in
	"$CLIENT_IB_BDF")
	    client_ib_dev="$(basename "$ibdev")"
	    ;;
	"$SERVER_IB_BDF")
	    server_ib_dev="$(basename "$ibdev")"
	    ;;
    esac
done

if [ -z "$client_ib_dev" ]; then
    echo "ERROR: Could not find client infiniband device" 1>&2
    exit 1
fi
if [ -z "$server_ib_dev" ]; then
    echo "ERROR: Could not find server infiniband device" 1>&2
    exit 1
fi

sudo rdma system set netns exclusive
sudo ip netns add peermemclient
sudo rdma dev set "$client_ib_dev" netns peermemclient
sudo ip netns exec peermemclient ip link set dev lo up
sudo ip link set netns peermemclient "$CLIENT_IFACE"
sudo ip netns exec peermemclient ip addr add dev "$CLIENT_IFACE" "$CLIENT_IP"
sudo ip netns exec peermemclient ip link set dev "$CLIENT_IFACE" up

sudo ip addr add dev "$SERVER_IFACE" "$SERVER_IP"
sudo ip link set dev "$SERVER_IFACE" up

sudo modprobe ib_umad # bro?
sudo modprobe nvidia-peermem

sudo_apt install -y opensm
sudo service opensm start

# Sometime after focal, ib_write_bw --use_cuda began requiring a device id
if use_cuda_needs_devid; then
    server_use_cuda_arg="--use_cuda=0"
    client_use_cuda_arg="--use_cuda=1"
else
    server_use_cuda_arg="--use_cuda"
    client_use_cuda_arg="--use_cuda"
fi
sudo ib_write_bw -a -d "$server_ib_dev" "$server_use_cuda_arg" &
srvpid=$!
# Give server a chance to start up
sleep 5
sudo ip netns exec peermemclient ib_write_bw -a \
     -d "$client_ib_dev" "${SERVER_IP%/*}" "$client_use_cuda_arg"
