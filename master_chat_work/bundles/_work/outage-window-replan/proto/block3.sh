set -u
mkdir -p /app && cp -r /srcdata /app/data
cd /d/proto
echo "== ORACLE"
for k in 1 2 3; do
  rm -rf /app/out; t0=$(date +%s)
  bash /solution/solve.sh > /tmp/solve_$k.log 2>&1; echo "solve rc $?"
  python3 -B drive_tests.py /tests/test_output.py > /tmp/drv_$k.log 2>/tmp/drv_err_$k.log
  grep '^SCORE' /tmp/drv_$k.log; echo "verifier_s $(( $(date +%s) - t0 ))"
done
grep 'negative' /tmp/drv_1.log
grep -c '^check .* ok' /tmp/solve_1.log
echo "== NOP"
rm -rf /app/out
python3 -B drive_tests.py /tests/test_output.py 2>/dev/null | grep -E 'negative|^SCORE'
echo ALL_DONE
