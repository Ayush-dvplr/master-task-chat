# 8caff6e blind solve, scored by the master (23 Oct 2026)
Bundle tree c3c5b97731b5 (= harden lp1 r2 eb6f232). Program: app/derive_report.py (696 lines, first full write ~3 min, no crash fix).
Scored in the verifier image (tests/Dockerfile), artifacts in /app/out, network none, judge removed (no trajectory/key): test_output 98/98 = tests 100. All 30 positive checks passed incl. every r2 lever (rate_composition_case, interval_credit_rounding_case, allowance_order_case, allowance_consumption_case, segment_rate_adder_mutation, allowance_ticks_mutation); no negative fired.
Verdict: gate FAIL (blind tests must be < 100). District back to harden; r2 levers are read correctly on first contact.
