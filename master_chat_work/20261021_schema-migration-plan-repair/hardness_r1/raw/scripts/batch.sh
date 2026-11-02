#!/bin/zsh
S=/tmp/smpr-hard-20261021T1730
cd $S
run() { python3 harness.py "$1" "$2" > /tmp/opencode-logs/smpr-hard-20261021T1730/$1.log 2>&1 }
python3 harness.py S1_stub stub > /tmp/opencode-logs/smpr-hard-20261021T1730/S1_stub.log 2>&1 &
ids=(S2_lazy S2_shipped S3_LV-MR-1 S3_LV-MR-2 S3_D S3_LV-MR-4 S3_LV-MR-5 S3_LV-MR-6 S3_LV-MR-7 S3_F S3_REPORT S3_C S3_LV-MR-1+LV-MR-6 S3_LV-MR-5+LV-MR-7 S4_careful S4b_composition_only)
i=0
for id in $ids; do
  run $id $S/solvers/$id.py &
  i=$((i+1))
  if (( i % 3 == 0 )); then wait; fi
done
wait
echo BATCH DONE
