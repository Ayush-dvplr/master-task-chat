#!/bin/bash
# one.sh <phase> <variant>
set -e
T="$(cd "$(dirname "$0")" && pwd)"; ph=$1; v=$2
if [ $ph = before ]; then tests="$T/before_tests/test_output.py"; data="$T/before_data"; else tests="$T/after_tests/test_output.py"; data="$T/after_data"; fi
ws="$T/ws/$ph/$v"; rm -rf "$ws"; mkdir -p "$ws"
if [ $v = a2 ]; then cp -R "$T/a2_$ph/." "$ws/"; else
  if [ $v = oracle ]; then cp "$T/after_solve.py" "$ws/solve.py"; else python3 "$T/mkvar.py" "$T/after_solve.py" "$ws/solve.py" $v; fi
  python3 "$ws/solve.py" --build "$data" "$ws/decode.py" "$ws/encode.py"
  python3 "$ws/solve.py" --emit-reports "$data" "$ws/out"
  rm "$ws/solve.py"
fi
python3 "$T/run.py" "$tests" "$ws" "$T/stub" > "$T/res/$ph.$v.json" 2> "$T/res/$ph.$v.err"
echo "done $ph $v"
