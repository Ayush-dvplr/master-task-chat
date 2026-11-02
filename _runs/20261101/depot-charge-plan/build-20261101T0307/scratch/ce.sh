set -u
cd /tmp
python3 -B /w/check_exact.py diff /d /w/sol/shipped
for c in hidden_61207 hidden_72931 hidden_84419 large_93503; do python3 -B /w/check_exact.py diff /w/$c/data /w/sol/$c; done
python3 -B /w/check_exact.py brute 300
rm -rf /tmp/ov1 /tmp/ov2
python3 -B /w/check_exact.py override /d /tmp/ov1
python3 -B /w/check_exact.py override /w/hidden_61207/data /tmp/ov2
echo ALL_DONE
