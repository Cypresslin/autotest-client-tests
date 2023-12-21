#!/bin/bash

#
#  Try an ensure that this script and parent won't be oom'd
#
set_max_oom_level()
{
	if [ -e /proc/self/oom_score_adj ]; then
		echo -900 > /proc/self/oom_score_adj
		echo -900 > /proc/$PPID/oom_score_adj
	elif [ -e /proc/self/oom_adj ]; then
		echo -14 > /proc/self/oom_adj
		echo -14 > /proc/$PPID/oom_adj
	fi
	#
	# Ensure oom killer kills the stressor hogs rather
	# than the wrong random process (e.g. autotest!)
	#
	if [ -e /proc/sys/vm/oom_kill_allocating_task ]; then
		echo 0 > /proc/sys/vm/oom_kill_allocating_task
	fi
}

#
#  Always add 1GB of swap to ensure swapping is exercised
#
SWPIMG=$HOME/stress-smoke-test-swap.img

#
#  Create 1GB swap file
#
swapoff ${SWPIMG} >& /dev/null
fallocate -l 1G ${SWPIMG}
if [ $? -ne 0 ]; then
	echo "FAILED: Count not create 1GB swap file, file system:"
	df
	exit 1
fi
chmod 0600 ${SWPIMG}
mkswap ${SWPIMG}
swapon ${SWPIMG}

set_max_oom_level
sleep 15
sync
