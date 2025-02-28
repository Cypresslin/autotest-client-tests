#!/usr/bin/env bash

# Pass timeout in seconds as an argument
timeout --preserve-status --signal INT $1 rtla timerlat hist

# Forward the exit code
exit $?
