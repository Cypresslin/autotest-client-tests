#!/bin/bash

#
#  Garbage collect swap file
#
SWPIMG=$HOME/stress-smoke-test-swap.img

swapoff ${SWPIMG}
rm ${SWPIMG}
