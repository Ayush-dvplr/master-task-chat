#!/bin/bash
# DRAFT only. Install this, the verifier, and allowed_signers under Ayush's
# separate protected account before use. Never put the private key in the
# master's account, ssh-agent, config, environment, or repo.
set -euo pipefail
umask 077

: "${TB_ROOT:?set absolute Terminal Bench root}"
: "${AYUSH_HOME:?set absolute /Users/mac root containing .config/opencode}"
: "${TRUST_DIR:?set Ayush-owned trust directory}"
: "${SIGNING_KEY:?set private signing key path, outside master access}"

case "$TB_ROOT:$AYUSH_HOME:$TRUST_DIR:$SIGNING_KEY" in
  *$'\n'*) echo "Newline in path" >&2; exit 2;;
esac
HERE=$(cd "$(dirname "$0")" && pwd -P)
VERIFIER="$HERE/verify_manifest.py"
mkdir -p "$TRUST_DIR"
candidate=$(mktemp "$TRUST_DIR/manifest.candidate.XXXXXX")
trap 'rm -f "$candidate" "$candidate.sig"' EXIT
python3 "$VERIFIER" snapshot --tb "$TB_ROOT" --home "$AYUSH_HOME" > "$candidate"

if [ -f "$TRUST_DIR/manifest.json" ]; then
  python3 - "$TRUST_DIR/manifest.json" "$candidate" <<'PY'
import json, sys
old = json.load(open(sys.argv[1]))["files"]
new = json.load(open(sys.argv[2]))["files"]
for path in sorted(old.keys() | new.keys()):
    if old.get(path) != new.get(path):
        print(f"{path}: {old.get(path, 'NEW')} -> {new.get(path, 'REMOVED')}")
PY
else
  echo "FIRST APPROVAL: review every file in the candidate inventory."
  python3 -m json.tool "$candidate"
fi

printf 'Type APPROVE after reviewing the exact changed files: '
read -r answer </dev/tty
[ "$answer" = APPROVE ] || { echo "Canceled" >&2; exit 1; }

# ssh-keygen prompts Ayush for the key passphrase on his terminal.
ssh-keygen -Y sign -f "$SIGNING_KEY" -n tb-master-rules-v1 "$candidate"
python3 "$VERIFIER" verify --tb "$TB_ROOT" --home "$AYUSH_HOME" \
  --manifest "$candidate" --signature "$candidate.sig" \
  --allowed-signers "$TRUST_DIR/allowed_signers"
cp "$candidate" "$TRUST_DIR/manifest.json.new"
cp "$candidate.sig" "$TRUST_DIR/manifest.json.sig.new"
mv "$TRUST_DIR/manifest.json.sig.new" "$TRUST_DIR/manifest.json.sig"
mv "$TRUST_DIR/manifest.json.new" "$TRUST_DIR/manifest.json"
python3 "$VERIFIER" verify --tb "$TB_ROOT" --home "$AYUSH_HOME" \
  --manifest "$TRUST_DIR/manifest.json" \
  --signature "$TRUST_DIR/manifest.json.sig" \
  --allowed-signers "$TRUST_DIR/allowed_signers"
echo "Approved current protected scope."
