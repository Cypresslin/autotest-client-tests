#!/bin/bash
###########################################################################################
## Copyright 2003, 2015 IBM Corp                                                          ##
##                                                                                        ##
## Redistribution and use in source and binary forms, with or without modification,       ##
## are permitted provided that the following conditions are met:                          ##
##	1.Redistributions of source code must retain the above copyright notice,          ##
##        this list of conditions and the following disclaimer.                           ##
##	2.Redistributions in binary form must reproduce the above copyright notice, this  ##
##        list of conditions and the following disclaimer in the documentation and/or     ##
##        other materials provided with the distribution.                                 ##
##                                                                                        ##
## THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS AND ANY EXPRESS       ##
## OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF        ##
## MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL ##
## THE AUTHOR OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,    ##
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF     ##
## SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) ##
## HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,  ##
## OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS  ##
## SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.                           ##
############################################################################################
### File : libXau.sh                                                           ##
##
### Description: This testcase tests the libXau package                        ##
##
### Author: Gopal Kalita <gokalita@in.ibm.com>                                 ##
###########################################################################################

#######cd $(dirname $0)
#LTPBIN=${LTPBIN%/shared}/libXau
source $LTPBIN/tc_utils.source
LIBXAU_TESTS_DIR="${LTPBIN%/shared}/libXau/tests"

function tc_local_setup()
{
	# check installation and environment 
	[ -f /usr/lib*/libXau.so.6 ]
	tc_break_if_bad $? "libXau is not installed"
}

function run_test()
{
    pushd $LIBXAU_TESTS_DIR >$stdout 2>$stderr
        TESTS=`ls`
        TST_TOTAL=`echo $TESTS | wc -w`
        for test in $TESTS; do
		tc_register "Test $test"
		./$test >$stdout 2>$stderr
		tc_pass_or_fail $? "Test $test failed" 
        done
    popd >$stdout 2>$stderr
}

#
# main
#
tc_setup
run_test 
