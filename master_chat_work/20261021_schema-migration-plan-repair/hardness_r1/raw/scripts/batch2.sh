#!/bin/zsh
S=/tmp/smpr-hard-20261021T1730
cd $S
run() { python3 harness.py "$1" "$2" > /tmp/opencode-logs/smpr-hard-20261021T1730/$1.log 2>&1 }
ids=(S3_LV-MR-5 S3_LV-MR-6 S3_LV-MR-7 S3_F S3_REPORT S3_C S3_LV-MR-1+LV-MR-6 S3_LV-MR-5+LV-MR-7 S4_careful SC1_claim_padding)
i=0
for id in $ids; do
  run $id $S/solvers2/$id.py &
  i=$((i+1))
  if (( i % 3 == 0 )); then wait; fi
done
run S1b_stub_default stub_default
wait
echo BATCH2 DONE
