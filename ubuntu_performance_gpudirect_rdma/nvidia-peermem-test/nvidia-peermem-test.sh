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

use_cuda_needs_devid() {
    if ib_write_bw --help | grep use_cuda=; then
	return 0
    fi
    return 1
}

# Avoid dpkg lock contention
sudo service unattended-upgrades stop || true

sudo apt-add-repository ppa:canonical-nvidia/perftest+cuda -y
sudo apt install perftest -y

if ! ldd /usr/bin/ib_write_bw | grep -q libcuda; then
    echo "ERROR: Installed perftest does not have CUDA support" 1>&2
    echo "ERROR: Is the PPA up to date?" 1>&2
    exit 1
fi

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

# IB Peer Memory is out of tree kernel patch carried in Ubuntu
# 4.15 -> 6.5. It is also provided by the Mellanox OFED modules.
if grep -q ib_register_peer_memory_client /proc/kallsyms; then
    mode=peermem
else
    mode=dma_buf
fi

sudo modprobe ib_umad # bro?
if [ "$mode" = "peermem" ]; then
    sudo modprobe nvidia-peermem
fi

sudo_apt install -y opensm
sudo service opensm start || sudo service opensmd start

# Sometime after focal, ib_write_bw --use_cuda began requiring a device id
if use_cuda_needs_devid; then
    server_args="--use_cuda=0"
    client_args="--use_cuda=1"
else
    server_args="--use_cuda"
    client_args="--use_cuda"
fi
if [ "$mode" = "dma_buf" ]; then
    server_args="$server_args --use_cuda_dmabuf"
    client_args="$client_args --use_cuda_dmabuf"
fi
sudo ib_write_bw -a -d "$server_ib_dev" $server_args &
srvpid=$!
# Give server a chance to start up
sleep 5
sudo ip netns exec peermemclient ib_write_bw -a \
     -d "$client_ib_dev" "${SERVER_IP%/*}" $client_args
