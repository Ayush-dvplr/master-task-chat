#!/usr/bin/env python3
"""Name the session that was started with a board prompt, in opencode or Codex.

usage: name_session.py SHA

Finds the session whose FIRST user message contains "Board id: `SHA`" (so the
master session, which only mentions the sha later, is never matched) and sets
its title to SHA. Tries Codex (~/.codex) and opencode; renames whichever match.
Codex auto-names a thread after its first turn, so prompts run this first thing
AND as their last step; the master can also run it when verifying.
"""
import base64
import datetime
import json
import os
import socket
import sqlite3
import struct
import subprocess
import sys
from pathlib import Path

CODEX = Path.home() / ".codex"


def daemon_set_name(tid: str, name: str) -> bool:
    """Rename through the running app-server daemon (JSON-RPC over WebSocket on
    its Unix socket). Open TUIs only see a rename made this way; a direct DB
    write is invisible to them and is overwritten from the daemon's memory."""
    sock_path = CODEX / "app-server-control" / "app-server-control.sock"
    if not sock_path.exists():
        return False
    try:
        s = socket.socket(socket.AF_UNIX)
        s.settimeout(15)
        s.connect(os.path.realpath(sock_path))
        key = base64.b64encode(os.urandom(16)).decode()
        s.sendall((f"GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                   f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                return False
            buf += chunk
        head, buf = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            return False

        def need(n: int) -> None:
            nonlocal buf
            while len(buf) < n:
                chunk = s.recv(65536)
                if not chunk:
                    raise ConnectionError("daemon closed the socket")
                buf += chunk

        def send(obj: dict) -> None:
            data = json.dumps(obj).encode()
            mask = os.urandom(4)
            n = len(data)
            hdr = b"\x81" + (bytes([0x80 | n]) if n < 126 else b"\xfe" + struct.pack(">H", n))
            s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

        def recv() -> dict:
            nonlocal buf
            while True:
                need(2)
                n, off = buf[1] & 127, 2
                if n == 126:
                    need(4)
                    n, off = struct.unpack(">H", buf[2:4])[0], 4
                elif n == 127:
                    need(10)
                    n, off = struct.unpack(">Q", buf[2:10])[0], 10
                need(off + n)
                op, payload, buf = buf[0] & 15, buf[off:off + n], buf[off + n:]
                if op == 1:
                    return json.loads(payload)
                if op == 8:
                    raise ConnectionError("daemon closed the websocket")

        send({"id": 1, "method": "initialize",
              "params": {"clientInfo": {"name": "name_session", "version": "1"}}})
        while recv().get("id") != 1:
            pass
        send({"method": "initialized"})
        send({"id": 2, "method": "thread/name/set", "params": {"threadId": tid, "name": name}})
        while True:
            r = recv()
            if r.get("id") == 2:
                s.close()
                if "error" in r:
                    print(f"codex daemon: {r['error']}")
                return "result" in r
    except (OSError, ConnectionError, ValueError) as e:
        print(f"codex daemon: unavailable ({e}); falling back to DB write")
        return False


def codex(sha: str, needle: str) -> list[str]:
    db = CODEX / "state_5.sqlite"
    if not db.exists():
        return []
    con = sqlite3.connect(db, timeout=10)
    rows = con.execute(
        "SELECT id FROM threads WHERE first_user_message LIKE ? ORDER BY created_at DESC LIMIT 1",
        (f"%{needle}%",),
    ).fetchall()
    ids = [r[0] for r in rows]
    for tid in ids:
        if daemon_set_name(tid, sha):
            continue
        con.execute("UPDATE threads SET name=? WHERE id=?", (sha, tid))
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        with open(CODEX / "session_index.jsonl", "a") as f:
            f.write(json.dumps({"id": tid, "thread_name": sha, "updated_at": stamp}) + "\n")
    con.commit()
    con.close()
    return ids


def opencode(sha: str, needle: str) -> list[str]:
    q = (
        "SELECT s.id FROM session s WHERE s.parent_id IS NULL AND ("
        "SELECT p.data FROM part p JOIN message m ON m.id = p.message_id "
        "WHERE p.session_id = s.id AND json_extract(m.data, '$.role') = 'user' "
        "ORDER BY p.time_created LIMIT 1) LIKE '%" + needle.replace("'", "''") + "%' "
        "ORDER BY s.time_created DESC LIMIT 1"
    )
    try:
        out = subprocess.run(["opencode", "db", q], capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"opencode: skipped ({e})")
        return []
    ids = [l.strip() for l in out.stdout.splitlines()[1:] if l.strip()]
    for sid in ids:
        subprocess.run(["opencode", "db", f"UPDATE session SET title='{sha}' WHERE id='{sid}'"],
                       capture_output=True, text=True, timeout=60)
    return ids


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isalnum():
        sys.exit(__doc__)
    sha = sys.argv[1]
    needle = f"Board id: `{sha}`"
    c, o = codex(sha, needle), opencode(sha, needle)
    print(f"codex: {c or 'no match'}")
    print(f"opencode: {o or 'no match'}")
    if not c and not o:
        print("NOT RENAMED: no session starts with this board id (note it and carry on)")


if __name__ == "__main__":
    main()
