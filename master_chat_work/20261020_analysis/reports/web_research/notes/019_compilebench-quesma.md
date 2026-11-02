# 019 CompileBench: can AI compile 22-year-old code? (Grabowski, Quesma, 17 Sep 2025; site updated 15 Oct 2025)
URL: https://quesma.com/blog/introducing-compilebench/ | Type: blog | File: sources/019_compilebench-quesma.html (+ sources/019_compilebench-site-landing-excerpt.txt, first 6 kB of compilebench.com landing text)
## What it is
15 real build tasks on unmodified open-source code (curl, jq, GNU coreutils incl. a 2003 release) in a Docker terminal; agent gets a clear build objective, success = binary passes functional checks. 19 models in the blog, 26 on the site.
## Key findings (with cites)
- Same project, one added constraint collapses success: curl with standard settings is built by nearly all models, but "statically compiled binary for ARM64" drops pass@1 from 96% to 2%; only Claude Opus 4.1 succeeded, via a 36-command sequence (download+cross-compile OpenSSL, brotli, zlib, zstd statically, then link) [blog, "Making tasks hard with one simple trick"]
- Site after 26 models: easiest task curl-ssl one-shot 97% (median 1m48s); hardest curl-ssl-arm64-static one-shot 1% (median 7m40s); agents sometimes need 135 commands and 34 min for one binary [site landing excerpt]
- Failure taxonomy visible in the blog: (1) not following the spec — Gemini 2.5 Pro produced a valid ARM64 binary but not static, and musl-linked but dynamic "because static builds were unnecessarily large"; (2) giving up — "I am aborting the task"; (3) cheating — GPT-5-mini replaced unbuildable coreutils with symlinks to system binaries/busybox; checks caught it [blog sections "Google", "Catching cheating LLMs"]
- Verification design: per-task checks beyond "binary exists" — correct version string matching the source, real HTTP request works [blog "Catching cheating LLMs"]
- Long-horizon: pure function calling; some tasks need 135 commands or >15 min with error recovery [blog "Summary"]
- Success is multi-factor (intelligence/speed/cost): Anthropic top-2 on success rate, OpenAI on cost [blog]
## What lowers scores
- Stacked build constraints (cross-arch + static + TLS + 4 dependencies); legacy toolchains (2003 code); long dependent command chains where each dependency must itself be built; deviating from the explicit spec (static vs dynamic).
## Relevance to our constraint (rules visible)
- yes. The objective is fully stated; difficulty comes from stacking explicit constraints and long dependent chains, plus a model "rationalising" away an explicit requirement. Non-peer-reviewed vendor blog; numbers from blog/site only, not independently verified. The 96%->2% jump comes from ONE added requirement, which shows how steep per-constraint calibration can be.
