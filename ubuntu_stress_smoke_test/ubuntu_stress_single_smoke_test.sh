#!/bin/bash

[ $# -lt 1 ] && echo "$0 requires STRESSOR name to be run" && exit 1
STRESSOR=${1}

# maximum bogo ops per stressor
MAX_BOGO_OPS=3000

SYS_ZSWAP_ENABLED=/sys/module/zswap/parameters/enabled

MEMORY=$((1024 * 1024 * 1024))
MEMFREE_KB=$(grep "MemFree" /proc/meminfo  | awk '{ print $2}')
MEMFREE=$((MEMFREE_KB * 1024))
MEMFREE_90PC=$((MEMFREE * 90 / 100))
MEMFREE_LESS_512MB=$((MEMFREE - (512 * 1024 * 1024)))
if [ $MEMFREE_90PC -gt $MEMFREE_LESS_512MB ]; then
	MEMORY=$MEMFREE_LESS_512MB
else
	MEMORY=$MEMFREE_90PC
fi
if [ $MEMORY -lt $((512 * 1024 * 1024)) ]; then
	MEMORY=$((512 * 1024 * 1024))
fi
echo "Free memory: $((MEMFREE / (1024 * 1024))) MB"
echo "Memory used: $((MEMORY / (1024 * 1024))) MB"

CGROUP_MEM1=/sys/fs/cgroup/memory/stress-ng-test
CGROUP_LIMIT1=${CGROUP_MEM1}/memory.limit_in_bytes
CGROUP_MEM2=/sys/fs/cgroup/stress-ng-test
CGROUP_LIMIT2=${CGROUP_MEM2}/memory.max
CGROUP=$(grep -o "^cgroup2 /sys/fs/cgroup " /proc/mounts | grep -o cgroup2)
if [ "$CGROUP" == "cgroup2" ]; then
	echo "Using cgroup version 2"
	CGROUP_MEM=${CGROUP_MEM2}
	CGROUP_LIMIT=${CGROUP_LIMIT2}
else
	echo "Using cgroup version 1"
	CGROUP_MEM=${CGROUP_MEM1}
	CGROUP_LIMIT=${CGROUP_LIMIT1}
fi
if [ ! -d ${CGROUP_MEM} ]; then
	mkdir ${CGROUP_MEM}
fi
echo $MEMORY > ${CGROUP_LIMIT}

#
# Stress test duration in seconds
#
DURATION=5
#
# Number of stress-ng instances per stressor
#
INSTANCES=4
#
# Generic stress-ng options
#
#STRESS_OPTIONS="--ignite-cpu --maximize --syslog --verbose --verify"
STRESS_OPTIONS="--ignite-cpu --syslog --verbose --verify --oomable"

rc=0
TMP_FILE=/tmp/stress-$$.log

secs_now()
{
	date "+%s"
}


passed=""
failed=""
skipped=""
oopsed=""
oomed=""
badret=""

#
# Enable Zswap if it is available and save original setting
# to restore later.
#
if [ -e ${SYS_ZSWAP_ENABLED} ]; then
	ORIGINAL_SYS_ZSWAP_SETTING=$(cat ${SYS_ZSWAP_ENABLED})
	echo Y > ${SYS_ZSWAP_ENABLED}
	SYS_ZSWAP_SETTING=$(cat ${SYS_ZSWAP_ENABLED})
else
	SYS_ZSWAP_SETTING="N"
fi

echo " "
echo "Machine Configuration"
echo "Physical Pages:  $(getconf _PHYS_PAGES)"
echo "Pages available: $(getconf _AVPHYS_PAGES)"
echo "Page Size:       $(getconf PAGE_SIZE)"
echo "Zswap enabled:   ${SYS_ZSWAP_SETTING}"
echo " "
echo "Free memory:"
free
echo " "
echo "Number of CPUs: $(getconf _NPROCESSORS_CONF)"
echo "Number of CPUs Online: $(getconf _NPROCESSORS_ONLN)"
echo
echo "Maximum bogo ops: ${MAX_BOGO_OPS}"
echo " "

#
#  Handle cases where cgroup settings are enabled or not
#
RUN_STRESS='./stress-ng'
if [ -e ${CGROUP_LIMIT} ]; then
	cgexec -g memory:stress-ng-test /bin/true
	#
	#  If cgexec works on trivial case then use it for stress-ng
	#
	if [ $? -eq 0 ]; then
		RUN_STRESS='cgexec -g memory:stress-ng-test ./stress-ng'
	else
		echo "WARNING: cgexec fails, is ${CGROUP} working correctly?"
	fi
fi

count=0
s1=$(secs_now)
count=$((count + 1))
dmesg -c >& /dev/null
echo "$STRESSOR STARTING"
${RUN_STRESS} -v -t ${DURATION} --${STRESSOR} ${INSTANCES} --${STRESSOR}-ops ${MAX_BOGO_OPS} ${STRESS_OPTIONS} >& ${TMP_FILE}
ret=$?
echo "$STRESSOR RETURNED $ret"

n=$(dmesg | grep "Out of memory:" | wc -l)
if [ $ret -ne 0 -a $n -gt 0 ]; then
	ret=88
fi

n=$(dmesg | grep "Oops" | wc -l)
if [ $n -gt 0 ]; then
	ret=99
fi

case $ret in
0)
	echo "$STRESSOR PASSED"
	passed="$passed $STRESSOR"
	;;
1)
	echo "$STRESSOR SKIPPED (test framework out of resources or test should not be run)"
	skipped="$skipped $STRESSOR"
	;;
2)
	echo "$STRESSOR FAILED"
	failed="$failed $STRESSOR"
	cat ${TMP_FILE}
	echo " "
	dmesg
	echo " "
	rc=1
	;;
3)
	echo "$STRESSOR SKIPPED (stressor out of resources)"
	skipped="$skipped $STRESSOR"
	;;
4)
	echo "$STRESSOR SKIPPED (stressor not implemented on this arch)"
	skipped="$skipped $STRESSOR"
	;;
5)
	echo "$STRESSOR SKIPPED (premature signal killed stressor)"
	skipped="$skipped $STRESSOR"
	;;
6)
	echo "$STRESSOR SKIPPED (premature child exit, this is a bug in the stress test)"
	skipped="$skipped $STRESSOR"
	;;
7)
	echo "$STRESSOR PASSED (child bogo-ops metrics were not accurate)"
	passed="$passed $STRESSOR"
	;;
88)
	echo "$STRESSOR OOMED (out of memory kills detected)"
	oomed="$oomed $STRESSOR"
	;;
99)
	echo "$STRESSOR FAILED (kernel oopsed)"
	oopsed="$oopsed $STRESSOR"
	dmesg
	echo " "
	rc=1
	;;
137)
	echo "$STRESSOR OOMED (out of memory kills detected)"
	oomed="$oomed $STRESSOR"
	;;
*)
	echo "$STRESSOR BADRET (unknown return status $ret)"
	badret="$badret $STRESSOR"
	dmesg
	echo " "
	;;
esac
rm -f ${TMP_FILE}
s2=$(secs_now)
dur=$((s2 - $s1))

echo " "
echo "Summary:"
echo "  Stressors run: $count"
echo "  Skipped: $(echo $skipped | wc -w), $skipped"
echo "  Failed:  $(echo $failed | wc -w), $failed"
echo "  Oopsed:  $(echo $oopsed | wc -w), $oopsed"
echo "  Oomed:   $(echo $oomed | wc -w), $oomed"
echo "  Passed:  $(echo $passed | wc -w), $passed"
echo "  Badret:  $(echo $badret | wc -w), $badret"
echo " "
echo "Tests took $dur seconds to run"

if [ -e ${SYS_ZSWAP_ENABLED} ]; then
	echo ${ORIGINAL_SYS_ZSWAP_SETTING} > ${SYS_ZSWAP_ENABLED}
fi

rmdir ${CGROUP_MEM} >& /dev/null

exit $rc
