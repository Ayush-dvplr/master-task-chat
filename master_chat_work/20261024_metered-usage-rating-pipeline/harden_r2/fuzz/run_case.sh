#!/bin/bash
# harden r2 adaptation: run_case.sh <W> <cases> <results> <workers> <name> [cpus]
W=$1
docker run --rm --name $5 --network none --cpus ${6:-4} -m 6g -v $W/tests:/tests:ro -v $W/fz:/fz -v $W/progs:/progs:ro warm-metered-usage-rating-pipeline:latest python3 /fz/fz_mu.py /fz/$2 /fz/$3 $4
