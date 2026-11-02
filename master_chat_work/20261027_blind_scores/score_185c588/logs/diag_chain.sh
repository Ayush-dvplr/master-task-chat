#!/bin/bash
D=/tmp/score_185c588/diag
touch /tmp/opencode-logs/locks/tariff-engine-audit-repair.lock /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
waitslot(){ while [ $(docker ps -q | wc -l) -ge 2 ]; do sleep 20; done; }
waitslot; echo "START tariff $(date +%T)"
docker run --rm --name s185-diag-tariff --cpus 2 --memory 4g -v $D/tariff_out:/app/out -v $D/diag.py:/diag.py:ro s185-tariff-engine-audit-repair-tests python /diag.py fresh_ledger_statements_feasible fresh_ledger_statement_due_exact fresh_ledger_statement_redeemed_exact rescaled_ledger_statements_feasible rescaled_ledger_statement_due_exact rescaled_ledger_statement_redeemed_exact relocated_ledger_statements_feasible relocated_ledger_statement_due_exact relocated_ledger_statement_redeemed_exact rotated_ledger_statements_feasible rotated_ledger_statement_due_exact rotated_ledger_statement_redeemed_exact api_ledger_statements_feasible api_ledger_statement_due_exact api_ledger_statement_redeemed_exact recoded_ledger_statements_feasible recoded_ledger_statement_due_exact recoded_ledger_statement_redeemed_exact renamed_ledger_statements_feasible renamed_ledger_statement_due_exact renamed_ledger_statement_redeemed_exact > $D/tariff_diag.txt 2>&1
echo "END tariff rc=$? $(date +%T)"
waitslot; echo "START cc $(date +%T)"
docker run --rm --name s185-diag-cc --cpus 2 --memory 4g -v $D/cc_out:/app/out -v $D/diag.py:/diag.py:ro s185-cold-chain-backbone-quote-tests python /diag.py fresh_1_core fresh_2_core fresh_3_core fresh_1_report fresh_2_report fresh_3_report fresh_1_summary fresh_2_summary fresh_3_summary fresh_networks_feasible fresh_rollups_follow_network rescaled_book_documents relocated_book_documents rerun_identical wide_1_core wide_2_core wide_3_core wide_books_report wide_books_summary wide_networks_feasible > $D/cc_diag.txt 2>&1
echo "END cc rc=$? $(date +%T)"
rm -f /tmp/opencode-logs/locks/tariff-engine-audit-repair.lock /tmp/opencode-logs/locks/cold-chain-backbone-quote.lock
echo ALL_DONE
