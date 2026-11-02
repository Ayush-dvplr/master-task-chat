#!/bin/bash
# adapted copy of test_depth kit run_case.sh for d62ffe6 (W and image changed, variant programs mounted)
W=/tmp/d62ffe6-fz-20261024T232559-c5fa
docker run --rm --name d62-fz-tf-20261024T232559-c5fa --network none --cpus 4 -m 6g -v $W/nj:/tests:ro -v $W/fz:/fz -v $W/agent:/progs/agent:ro -v $W/var:/progs/var:ro d62-tf-verifier python3 /fz/fz_tf.py /fz/tf_cases.jsonl /fz/tf_out.jsonl 4
