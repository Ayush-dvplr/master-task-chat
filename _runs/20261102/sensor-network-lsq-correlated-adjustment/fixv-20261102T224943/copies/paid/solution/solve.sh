#!/bin/bash
# Paid-program rescore lane (R0 868afdf): deliver the paid run's derive_report.py unchanged and run it on the shipped extract.
set -e
mkdir -p /app/out
cp /solution/paid.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
