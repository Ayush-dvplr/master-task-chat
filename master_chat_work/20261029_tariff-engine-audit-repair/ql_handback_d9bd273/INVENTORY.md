# INVENTORY: QL zip tariff-engine-audit-repair (board d9bd273)

- Zip: `master_chat_work/_ql/tariff-engine-audit-repair/20261029T0235_zip/tariff-engine-audit-repair.zip`, sha256 `6933097ffa65cfb84d7596249ccedfe9a0b62a4042176ebb551f778e6e846b60` (matches prompt; LOG 03:59).
- Safety: 142 entries, 0 absolute paths, 0 `..` components, 0 symlinks (python zipfile external_attr check, LOG 03:59). Not an unsafe zip.
- Unzipped with `-x '__MACOSX/*'` into `/tmp/ql-tariff-engine-audit-repair-20261029T0359/x/`. Bundle root (holds task.toml): `x/tariff-engine-audit-repair/`.
- Bundle tree sha excluding trajectories/ (`find . -type f -not -path './trajectories/*' -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`): **dfd8e457d203** (REQUEST.md states the same). Frozen / TASKS_INPUT / LAST_QC_COPY f054899 / BUNDLE / Output_RFP excl. trajectories: **0de116d29fdb** (all five equal, LOG 04:00).
- `trajectories/` exists: yes. Runs: `claude-opus-5/run_1` (one run) plus `claude-opus-5/pass_summary.json`.
- Files: 51 (of which 21 under trajectories/).
- Extra files vs Output_RFP layout: none. Files in Output_RFP missing from zip: none (same 51-path list).

## Files
| path | bytes | sha256 |
|---|---|---|
| environment/Dockerfile | 891 | `e467b0a6228a103e2c3442b44fdf40149d3e8117921a1910a657b98fe9c2b278` |
| environment/ci/accounts.csv | 87731 | `e704cdd3952e0eeefbef402ddc31ee07527cc0bb46ecbbbfdf098cb266f99585` |
| environment/ci/api_contract.md | 16482 | `1e7c3879732b831da9c3c7e745ef07b97317b85f01276098af8d99357fa3df63` |
| environment/ci/billing_periods.csv | 92310 | `f632bbc6515c531d8dd85a091d0179e4cdd123c8b4f12a053f2d96987a19a8e3` |
| environment/ci/build_config.json | 288 | `a329a857ffea2af3f5c8a15e2db27ded73aab78d80af1e797278885a3cc8d4bc` |
| environment/ci/failing_tests.log | 757515 | `86fd976459d82f8183b20132be2b1a033c64a20f525a07daddd4bd8a81713168` |
| environment/ci/lint_report.json | 61250 | `80147898535abf0b7ec021564a6ec1e71a567e43d7583cda99db5723cace0649` |
| environment/ci/meter_reads.jsonl | 1061380 | `512f37ec00ade105b5cd7d69b4319a5279e2b37db37d058467432d7991bce495` |
| environment/ci/package_manifest.json | 194 | `5f44079b5d01281351f6473065dfd466af68db44dbfbe962b6ed54105875846a` |
| environment/ci/rate_card.json | 2132 | `5c6b9661bcb1e984769e97bc156a810a9812cf240cbca6f4000c43082015b09c` |
| environment/ci/regression_cases.jsonl | 1560870 | `806b7d343e7d94052dec8ed54d20144663ffa16af529b045118e0480ae35ddb1` |
| environment/ci/vouchers.csv | 3553 | `ed793dbe2cca68c6303ed3cc114655041ce61dc971233f66c0365ee74d2e8cce` |
| environment/repo/README.md | 639 | `830c48370c674e8faf50e461409affd43257a3ae2c9ee19e2de0d01a3de1d2d7` |
| environment/repo/pyproject.toml | 202 | `eae14b0f42447d4bf977603869e9d9c45716352416da8401da904c16ef0d2aa3` |
| environment/repo/src/tariff/__init__.py | 175 | `471e26b3a6ca3d11343a2e12332e203dd855d30454063aee2d6922d6eb977b42` |
| environment/repo/src/tariff/__main__.py | 294 | `b13a2a7ef75940733620dea9dcd01e0a0f6629115802b771b12c4773dd60463d` |
| environment/repo/src/tariff/core.py | 1564 | `c9b3726953fe570abedad04cce46a0dd196286ee7502bca29d45c090d00cc1f0` |
| environment/repo/src/tariff/parser.py | 2471 | `9f07d3dbef555ddb908b9029e270bdc126d50e2d99e3bfe186f07752c94e6249` |
| environment/repo/src/tariff/report.py | 3325 | `feec81ede62615e16d37f42b9eed83f1efd201059b5d084bfdc640d15cb5144f` |
| environment/repo/tests/test_visible.py | 5670 | `067ececf928c93be3b98a81dd66196152b331164980f479d60d195cec84e6eae` |
| instruction.md | 1579 | `bb5942a09cee429751f8e82b846483def17466f1fbf127b552626821c744051f` |
| solution/TRUTH.md | 25319 | `5dddc3564aa827b14a66d038931bf6525750c3f9ebae154d74bb0d48d7d6217d` |
| solution/solve.py | 45338 | `b3a65364000d8b256a7002a16efbb2b16cdbf92499ffdea2d51fca09e52fa93b` |
| solution/solve.sh | 77 | `25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680` |
| task.toml | 1584 | `cba1a9aa3de49bb97862a927b01a02f723f732f6c65c635884f5c4a93d0942d3` |
| tests/Dockerfile | 291 | `09dc7fb726b14698b841fd88d5734f46195c0e22f43c57e3a5943085b37339b9` |
| tests/judge.toml | 5403 | `1991e88cc21cb39a8c15ab864e1669e5e1fa3dbbd353c7ec5d5c0f6ed66cc34c` |
| tests/reward.toml | 188 | `5a67509eadcdfdd7eb96983f8492bb279723d9b735d11d2e18a7510ed8a29667` |
| tests/test.sh | 304 | `5302b9b87341ed25694888cd4c3392a46a6bd25b6f1a31fd1c6e9e109d46efd8` |
| tests/test_output.py | 740432 | `5dc07e5e2d0c902a46236a7d1251878215564e4c6659818ceb73b465d641640b` |
| trajectories/claude-opus-5/pass_summary.json | 370 | `971125cbeb76900f9ab834d0742b696b189c5968b8ec6a815a72c3d9ee19b713` |
| trajectories/claude-opus-5/run_1/agent/trajectory.json | 296076 | `d7029191fa0b9ed4fdc95af1ba5b476fa3b82581f894c65838be9f73743d511b` |
| trajectories/claude-opus-5/run_1/artifacts/app/out/module_core.json | 2753 | `de6a8704d739c6cc387cdc6d30fd7bd8441fd43818aaf1daa927d814d9927a32` |
| trajectories/claude-opus-5/run_1/artifacts/app/out/module_parser.json | 1072 | `02e84fdb6d48bc20a3323200c09093410d4724148e0a0c9072a50f6cef5da85c` |
| trajectories/claude-opus-5/run_1/artifacts/app/out/module_report.json | 1398 | `0bed483a1d1c2c07d3da23c0543f9b905da32ee8e11273a8e796c050f3dad406` |
| trajectories/claude-opus-5/run_1/artifacts/app/out/patched-repo.zip | 28325 | `0bddd0fbaccddad08dea622fc0ffe809e3bda7b19d229a6af8e38f42e3ca6e95` |
| trajectories/claude-opus-5/run_1/artifacts/app/out/repair-report.json | 11209 | `6ce3fa6ee07f6ef1c366855d6533b6eedbeb5ca725f4297c48e9053b92a2970d` |
| trajectories/claude-opus-5/run_1/artifacts/app/out/summary.json | 642 | `984ee0838208781b67b1c7883fb28469ec35a9157762633c81a3fc1d2c2fa879` |
| trajectories/claude-opus-5/run_1/artifacts/app/out/test_fixes.json | 263878 | `10225bb16931ef6ce0a9c411227b569f5077aff84d7faf124d79f1e000505bb5` |
| trajectories/claude-opus-5/run_1/artifacts/logs/agent/trajectory.json | 296076 | `d7029191fa0b9ed4fdc95af1ba5b476fa3b82581f894c65838be9f73743d511b` |
| trajectories/claude-opus-5/run_1/artifacts/manifest.json | 1688 | `0823ccaeec6e5b0393d1713b39613d1ac4171b595d46c287df8f36008ff01d05` |
| trajectories/claude-opus-5/run_1/config.json | 1571 | `8a2e2d1f5eb8731054bb0a1beb0f28c96721feb869415cc61996aa021aafacd3` |
| trajectories/claude-opus-5/run_1/report.json | 20895 | `80ffd0c8abe0e2526d92474092e2432d5a2d869807fd9965e774e29e4b4ca1de` |
| trajectories/claude-opus-5/run_1/result.json | 4972 | `210342d87568474d35cf2d6898d23560074905d953ac787a5fb381e5a05b3333` |
| trajectories/claude-opus-5/run_1/trajectory_usage.json | 1073 | `9de614885dd06c9516665eb100defb0891bbe731cea2010090a7352ff8226778` |
| trajectories/claude-opus-5/run_1/verifier/ctrf.json | 14211 | `5f6e38e932fd745f6d1d9bf548641231fbe04342695fb213d96a8af0b0118a1d` |
| trajectories/claude-opus-5/run_1/verifier/reward-details.json | 46539 | `bddaa1ab86d1d0e6e23f8acf144a740d8393f445443afbd534fe9b8ad2979848` |
| trajectories/claude-opus-5/run_1/verifier/reward.json | 22 | `d4698f1deec7b83cf24c3357f7d83e8d7924d94194c2666eaeba03877356b617` |
| trajectories/claude-opus-5/run_1/verifier/reward_raw.json | 22 | `350e3064aebaffe2d3c412bbe332a88eb9ebd18e34695a0f606fcbc0f54713fb` |
| trajectories/claude-opus-5/run_1/verifier/score.json | 7252 | `c6d386d8b8223320e20f73a53466bbffb76aa2ffc0285cd1e45a46698dbc0f55` |
| trajectories/claude-opus-5/run_1/verifier/test-stdout.txt | 15 | `deed9bb36cc1a2d83ad895c4b1fe4406434eafb45c0cbef4f5139a7ba71791f2` |

## Packaging junk excluded (71 `__MACOSX/` AppleDouble entries, 163 bytes each)

- __MACOSX/._tariff-engine-audit-repair
- __MACOSX/tariff-engine-audit-repair/._tests
- __MACOSX/tariff-engine-audit-repair/._solution
- __MACOSX/tariff-engine-audit-repair/._instruction.md
- __MACOSX/tariff-engine-audit-repair/._environment
- __MACOSX/tariff-engine-audit-repair/._task.toml
- __MACOSX/tariff-engine-audit-repair/._trajectories
- __MACOSX/tariff-engine-audit-repair/tests/._Dockerfile
- __MACOSX/tariff-engine-audit-repair/tests/._test_output.py
- __MACOSX/tariff-engine-audit-repair/tests/._reward.toml
- __MACOSX/tariff-engine-audit-repair/tests/._test.sh
- __MACOSX/tariff-engine-audit-repair/tests/._judge.toml
- __MACOSX/tariff-engine-audit-repair/solution/._TRUTH.md
- __MACOSX/tariff-engine-audit-repair/solution/._solve.sh
- __MACOSX/tariff-engine-audit-repair/solution/._solve.py
- __MACOSX/tariff-engine-audit-repair/environment/._Dockerfile
- __MACOSX/tariff-engine-audit-repair/environment/._ci
- __MACOSX/tariff-engine-audit-repair/environment/._repo
- __MACOSX/tariff-engine-audit-repair/trajectories/._claude-opus-5
- __MACOSX/tariff-engine-audit-repair/environment/ci/._package_manifest.json
- __MACOSX/tariff-engine-audit-repair/environment/ci/._accounts.csv
- __MACOSX/tariff-engine-audit-repair/environment/ci/._failing_tests.log
- __MACOSX/tariff-engine-audit-repair/environment/ci/._rate_card.json
- __MACOSX/tariff-engine-audit-repair/environment/ci/._build_config.json
- __MACOSX/tariff-engine-audit-repair/environment/ci/._billing_periods.csv
- __MACOSX/tariff-engine-audit-repair/environment/ci/._regression_cases.jsonl
- __MACOSX/tariff-engine-audit-repair/environment/ci/._meter_reads.jsonl
- __MACOSX/tariff-engine-audit-repair/environment/ci/._api_contract.md
- __MACOSX/tariff-engine-audit-repair/environment/ci/._lint_report.json
- __MACOSX/tariff-engine-audit-repair/environment/ci/._vouchers.csv
- __MACOSX/tariff-engine-audit-repair/environment/repo/._pyproject.toml
- __MACOSX/tariff-engine-audit-repair/environment/repo/._tests
- __MACOSX/tariff-engine-audit-repair/environment/repo/._README.md
- __MACOSX/tariff-engine-audit-repair/environment/repo/._src
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/._pass_summary.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/._run_1
- __MACOSX/tariff-engine-audit-repair/environment/repo/tests/._test_visible.py
- __MACOSX/tariff-engine-audit-repair/environment/repo/src/._tariff
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/._artifacts
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/._report.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/._trajectory_usage.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/._result.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/._config.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/._agent
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/._verifier
- __MACOSX/tariff-engine-audit-repair/environment/repo/src/tariff/.___init__.py
- __MACOSX/tariff-engine-audit-repair/environment/repo/src/tariff/._core.py
- __MACOSX/tariff-engine-audit-repair/environment/repo/src/tariff/._parser.py
- __MACOSX/tariff-engine-audit-repair/environment/repo/src/tariff/.___main__.py
- __MACOSX/tariff-engine-audit-repair/environment/repo/src/tariff/._report.py
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/._app
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/._logs
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/._manifest.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/agent/._trajectory.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/verifier/._reward_raw.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/verifier/._test-stdout.txt
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/verifier/._reward.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/verifier/._score.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/verifier/._ctrf.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/verifier/._reward-details.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/app/._out
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/logs/._artifacts
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/logs/._agent
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/app/out/._summary.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/app/out/._module_parser.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/app/out/._patched-repo.zip
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/app/out/._test_fixes.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/app/out/._repair-report.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/app/out/._module_report.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/app/out/._module_core.json
- __MACOSX/tariff-engine-audit-repair/trajectories/claude-opus-5/run_1/artifacts/logs/agent/._trajectory.json

## Lessons for the master
none
