cd "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/cleanroom-window-schedule"
for f in rule_mut/*.py; do
  m=$(basename $f .py)
  echo "== $m $(date +%T)"
  python3 -B run_tests.py $f --json tmp/rule/$m.json > tmp/rule/$m.log 2>&1
  tail -1 tmp/rule/$m.log
done
echo ALL_DONE
