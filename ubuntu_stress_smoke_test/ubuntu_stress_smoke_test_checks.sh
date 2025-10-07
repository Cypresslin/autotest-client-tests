#!/bin/bash

# Maximum machine age was set to 5 years by Colin in 2020, let's use 2015 as the bar
MIN_YEAR=2011
# minimum required memory in MB
MIN_MEM=$((1 * 1024 + 512))
# minimum free disk required in GB
MIN_DISK=$((3))

check_message()
{
	echo "NOTE: $1, skipping test"
}

check_machine()
{
	hostname=$(hostname)
	processor=$(uname -m)
	skip=0
	case "$processor" in
	i386 | i486 | i586 | i686 | x86_64)
		datecheck=1

		manufacturer=$(dmidecode -s system-manufacturer)
		if [ "$manufacturer" == "QEMU" ] || [ "$manufacturer" == "Xen" ]; then
			echo "$manufacturer instance, no firmware date checking"
			datecheck=0
		fi

		vendor=$(dmidecode -t 0x0000 | grep Vendor: | awk '{ print $2}')
		if [ -z "$vendor" ]; then
			vendor=$(dmidecode -t 0x000e | grep Vendor: | awk '{ print $2}')
		fi

		case "$vendor" in
		unknown | Unknown)
			check_message "Unknown BIOS vendor, ignoring machine"
			skip=1
			datecheck=0
			;;
		SeaBIOS)
			echo "SeaBIOS BIOS, using a VM, no date checking"
			datecheck=0
			;;
		*)
			;;
		esac

		if [ $datecheck -eq 1 ]; then
			date=$(dmidecode -t 0x0000 | grep "Release Date:" | cut -d'/' -f3)
			if [ -z "$date" ]; then
				date=$(dmidecode -t 0x000e | grep "Release Date:" | cut -d'/' -f3)
			fi
			if [ ! -z "$date" ]; then
				if [ $date -lt $MIN_YEAR ]; then
					check_message "BIOS indicates machine was released in $date, older then $MIN_YEAR."
					skip=1
				fi
			fi
		fi
		;;
	*)
		echo "other"
		;;
	esac

	mem=$(free | grep Mem: | awk '{print $2}')
	mem=$((mem / 1024))
	if [ $mem -lt $MIN_MEM ]; then
		check_message "Machine has only $mem MB memory, requires at least $MIN_MEM MB"
		skip=1
	fi
	disk=$(df . -B 1024  | awk '{print $4}' | tail -1)
	disk=$((disk / 1048576))
	if [ $disk -lt $MIN_DISK ]; then
		check_message "Machine has only $disk GB free disk space, requires at least $MIN_DISK GB"
		skip=1
	fi

	if [ $skip -ne 0 ]; then
		exit 1
	fi

	echo "$hostname: $processor $mem MB memory, $disk GB disk"
}

check_machine
