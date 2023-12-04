#!/bin/bash 

#
#  Garbage collect swap file
#
SWPIMG=$PWD/swap.img

swapoff ${SWPIMG}
rm ${SWPIMG}

exit $rc
