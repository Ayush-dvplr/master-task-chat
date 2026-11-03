RQ9 RESULT: installed DCP 3.2.0 (opencode reply pasted by Ayush, 3 Nov 2026; condensed by Claude, full config.ts stays on the Mac at ~/.cache/opencode/packages/@tarquinen/opencode-dcp@3.2.0/node_modules/@tarquinen/opencode-dcp/lib/config.ts)

1. Installed: 3.2.0 (pinned path and an @latest path, both 3.2.0). No dcp.schema.json inside; defaults live in lib/config.ts and dist/index.js (they match).
2. Defaults: same as the master schema (F1.9): maxContextLimit 100000, minContextLimit 50000, permission allow, mode range, protectUserMessages false, protectTags false, protectedFilePatterns empty, turnProtection off (4 turns), manualMode off, customPrompts off, nudgeFrequency 5, iterationNudgeThreshold 15, nudgeForce soft, compress.protectedTools task, skill, todowrite, todoread; commands.protectedTools adds compress, batch, plan_enter, plan_exit, write, edit; dedup and purgeErrors (4 turns) on.
3. Supported and how they really work:
   a. compress.protectUserMessages: appends the FIRST non empty text part of each user message, word for word, to the compression summary (not every part).
   b. compress.protectTags: text inside <protect>...</protect> in USER messages is appended to the summary.
   c. protectedFilePatterns: globs on file paths of tool calls; protects those tool results from compression and pruning.
   d. turnProtection: keeps recent TOOL CALLS out of pruning only; it does not stop compression of recent conversation.
   e. manualMode: blocks model started compression until triggered by hand (/dcp commands); automatic dedup and error purge keep running unless automaticStrategies is false.
   f. compress.modelMaxLimits and modelMinLimits: per "providerID/modelID", a number or a percent string like "60%".
   g. maxContextLimit and minContextLimit also accept percent strings.
4. CONFIG LAYERS (important for S6 and for different settings per session type), applied in order, later wins:
   a. global ~/.config/opencode/dcp.jsonc (created empty if missing),
   b. $OPENCODE_CONFIG_DIR/dcp.jsonc if that environment variable is set,
   c. project: the NEAREST .opencode/dcp.jsonc found walking UP from the session's working directory.
   List options (protectedTools, protectedFilePatterns) are merged (added), not replaced.
