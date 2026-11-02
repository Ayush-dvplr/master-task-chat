#!/bin/zsh
cd "$(dirname "$0")/../.."
for m in raw_tuned raw_exact; do
  python3 -B run_tests.py mutants/$m.py --json tmp/cost2/$m.json > tmp/cost2/$m.log 2>&1
  echo "$m done $(date +%T)"
done
echo ALL_DONE
