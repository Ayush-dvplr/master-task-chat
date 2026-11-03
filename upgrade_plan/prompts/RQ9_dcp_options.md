RQ9 PROMPT (paste into a NEW opencode session, GPT Sol 6.1)

```text
Read only. Do not change any file. Do not run subagents. Do all work in this chat.
1. Find where the opencode plugin @tarquinen/opencode-dcp version 3.2.0 is installed (look under ~/.cache/opencode, ~/.config/opencode/node_modules, ~/.local/share/opencode and the opencode plugin cache; run: find ~ -path "*opencode-dcp*" -name "package.json" 2>/dev/null | head).
2. Print its package.json version, and the full contents of its dcp.schema.json (or the file that defines its default config).
3. List the names of every config option it supports and its default value, as plain text.
4. Say whether it supports: compress.protectUserMessages, compress.protectTags, protectedFilePatterns, turnProtection, manualMode, compress.modelMaxLimits.
```
