#!/bin/bash
set -e
mkdir -p /app/out
cp ${SOLUTION_ROOT:-/solution}/saved_out/* /app/out/
