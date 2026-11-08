# LeanCoder measured runs

All numbers below are real measurements from live runs on 2026-11-08
20:34-20:42 UTC (2026-11-09 01:34-01:42 PKT). Nothing here is estimated,
projected, or invented. Failed tasks are shown as failures.

## Setup

- Model: ollama/qwen2.5-coder:3b, Qwen2.5-Coder 3B Instruct, Q4_K_M
  quantisation, 2.1 GB on disk. A 7b model was not used: the machine has
  8 GB RAM with about 2 GB free, so a 7b model would not fit safely.
- Ollama 0.40.15, installed locally under the workspace (the system
  /usr/local is wiped on VM restart, so the install lives in the
  workspace, not in /usr/local). The Ollama registry pull failed twice
  (first run: EOF after 10 minutes on the manifest request; second run:
  stuck on the manifest request with nothing downloaded), while the
  same registry endpoint answered curl in under 1 second. Fallback
  used: the GGUF file was downloaded from HuggingFace
  (Qwen/Qwen2.5-Coder-3B-Instruct-GGUF,
  qwen2.5-coder-3b-instruct-q4_k_m.gguf, 2.0 GB, sha256
  724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7)
  and created as an Ollama model with a local Modelfile.
- Bifrost v2.5.0 (HTTP transport), official binary fetched with npx
  (@maximhq/bifrost), started on http://127.0.0.1:8080 with a
  config.json that registers the local Ollama provider
  (ollama_key_config url http://127.0.0.1:11434) and one local-only
  virtual key for the gateway. No provider API key exists or was used:
  the model runs locally, so there is nothing to pay for and no key
  to leak. The virtual key value is a local placeholder and is not
  written in this repo.
- Smoke tests before the measured runs, all through the real paths:
  Ollama direct, 2+2 answered 4 (42 prompt, 2 completion, 44 total);
  through Bifrost with the virtual key header, 2+2 answered 4
  (42 prompt, 2 completion, 44 total, 1.2 seconds); through Bifrost
  with a Bearer header, 3+3 answered 6 (42 prompt, 2 completion,
  44 total). The LeanCoder client sends Bearer, so the Bearer test
  is the one that matters, and it passed.
- Every run used --auto-approve demo mode, one task per process, and
  saved its ledger trace. The 10 traces are committed in
  examples/measured-traces/ and replayed by verify.py.

## Results: lean mode vs direct mode

Each task ran once in lean mode (only the files the task needs are
sent) and once in direct mode (the whole repo is sent every call).

| Task | Lean tokens (prompt + completion) | Lean result | Lean steps | Direct tokens (prompt + completion) | Direct result | Direct steps |
| --- | --- | --- | --- | --- | --- | --- |
| task1_add_function | 860 (484 + 376) | passed | 2 | 1321 (741 + 580) | passed | 3 |
| task2_fix_off_by_one | 596 (466 + 130) | passed | 2 | 278 (218 + 60) | passed | 1 |
| task3_write_tests | 305 (193 + 112) | passed | 1 | 408 (300 + 108) | passed | 1 |
| task4_refactor_dupe | 481 (331 + 150) | passed | 1 | 1491 (1053 + 438) | failed | 3 |
| task5_input_validation | 1102 (708 + 394) | failed | 3 | 312 (216 + 96) | passed | 1 |
| **Total** | **3344** | **4 of 5 passed** | | **3810** | **4 of 5 passed** | |

Tokens per passing task: lean 560.5, direct 579.75.

Elapsed time: lean runs 83, 36, 33, 39, 82 seconds (273 seconds
total); direct runs 105, 12, 24, 75, 18 seconds (234 seconds total).
All 10 runs together took 507 seconds.

## Honest reading

- Lean mode used fewer tokens in total (3344 vs 3810, 12 percent
  fewer) and fewer tokens per passing task (560.5 vs 579.75,
  3 percent fewer). The advantage is real but small with this 3b
  model. It is not a win on every task.
- Lean won on tasks 1, 3, and 4. Task 1: 860 vs 1321. Task 3:
  305 vs 408. Task 4: 481 vs 1491, and lean passed where direct
  failed.
- Lean lost on task 2: 596 vs 278. Lean needed a second step to
  fix its first patch, and that extra model call cost more than
  the smaller prompt saved. Direct passed in one step.
- Lean failed task 5 (1102 tokens, 3 steps, max steps reached
  without passing tests) while direct passed it in 1 step and
  312 tokens. Direct failed task 4 (1491 tokens, 3 steps) while
  lean passed it in 1 step and 481 tokens.
- Both failures are model failures, not infrastructure failures:
  the error in both cases is "Max steps reached without passing
  tests." after 3 steps.
- The model is not deterministic. The same task in the same mode
  gave different results on repeat runs: task1 in lean mode passed
  in 2 steps and 860 tokens in the measured run, failed in 3 steps
  and 1297 tokens in the first private-task attempt, then passed
  in 2 steps and 854 tokens on retry. Treat every number here as
  one measured run, not a stable average.
- Token counts are as reported by the model endpoint through
  Bifrost. Bifrost prompt caching served repeated prompt prefixes
  from cache on later calls; the reported prompt token counts
  include cached tokens and are not split out here.
- Cost is 0.0 for every run: the model runs locally, so there is
  no per-token price. No cost figure is invented.

## verify.py

`python3 verify.py` on the 10 recorded traces: PASS, exit 0, 2.8
seconds. 69 unit tests run, passed. 10 of 10 traces replayed and
matched (patches re-applied, hidden tests re-run, ledger token
totals checked). The two failed tasks replay as failures too,
which is the point: replay checks what happened, it does not
turn failures into passes.

## Outage drill

The client was pointed at a dead gateway
(BIFROST_BASE_URL=http://127.0.0.1:9999, nothing listening).
Task task2_fix_off_by_one, lean mode: passed False, 0 tokens, and
the error reported plainly: "Could not reach Bifrost at
http://127.0.0.1:9999. Start Bifrost first, then retry." No
invented success, no silent fallback to another provider. The
drill ledger was kept outside the repo and is not committed.

## Private-task proof

A copy of task1 was marked PRIVATE and run twice.

- With a remote model name (gemini/gemini-2.5-flash): refused
  before any model call. Passed False, 0 model calls, 0 tokens,
  error: "Private task refused: private code runs only on a local
  model, and the configured model is not local. Use an ollama/
  model."
- With the local model (ollama/qwen2.5-coder:3b): it ran.
  First attempt failed after 3 steps, 1297 tokens. Retry passed
  in 2 steps, 854 tokens. The local run is real work, not a
  bypass: the model was called, patches were written, and the
  hidden tests ran.

## Limits

- One model only: ollama/qwen2.5-coder:3b. No Gemini or other
  remote model was run, because no provider key is on file.
- One run per task per mode. No averages, no repeats, except the
  private-task retry noted above.
- The 3b model is small and inconsistent. A bigger model would
  likely pass more tasks, but it does not fit this machine.
- A live run from zero is not under 5 minutes: it needs Ollama
  and Bifrost running and the model downloaded. The under-2-minute
  judge path is verify.py, which replays the recorded traces
  offline with no key, no Docker, and no Bifrost.

## Batch 4: repeated runs with the improved agent

All numbers below are real measurements from live runs on 2026-11-08
20:54-21:26 UTC (2026-11-09 01:54-02:26 PKT). Nothing here is
estimated, projected, or invented. Failed tasks are shown as
failures, and no run was dropped.

### Agent changes

- Max steps raised from 3 to 5.
- The failing test output was already sent back to the model after
  a failed test run (present since Batch 1, verified and kept).
  New in Batch 4: the files are re-read on every step, so the model
  sees the current file state after its own patch instead of the
  original starter files.
- Budget hard stop, approval gates, sandbox confinement, and the
  private-task local-only rule are unchanged. The 5 tasks and the
  hidden tests are unchanged.

### Setup

- Same setup as Batch 3: model ollama/qwen2.5-coder:3b, Ollama
  0.40.15, Bifrost v2.5.0 on http://127.0.0.1:8080. Both services
  were still running and were smoke tested before the runs (2+2
  answered 4 directly through Ollama and through Bifrost). Nothing
  was reinstalled or restarted.
- Every run used --auto-approve demo mode, one task per process,
  and saved its ledger trace. The 30 traces are committed in
  examples/measured-traces-batch4/ and replayed by verify.py.

### Results: lean mode vs direct mode, 3 repeats each

Each task ran 3 times in lean mode and 3 times in direct mode.
Mean tokens are the mean of the 3 repeats, with the 3 individual
totals in brackets.

| Task | Lean mean tokens | Lean pass | Direct mean tokens | Direct pass | Lower mean |
| --- | --- | --- | --- | --- | --- |
| task1_add_function | 1555.0 (1204, 1249, 2212) | 2 of 3 | 1130.0 (979, 792, 1619) | 3 of 3 | direct |
| task2_fix_off_by_one | 424.3 (288, 709, 276) | 3 of 3 | 895.7 (1687, 278, 722) | 2 of 3 | lean |
| task3_write_tests | 1027.3 (2221, 453, 408) | 2 of 3 | 556.3 (408, 853, 408) | 3 of 3 | direct |
| task4_refactor_dupe | 1589.7 (2652, 1655, 462) | 2 of 3 | 1174.7 (459, 472, 2593) | 3 of 3 | direct |
| task5_input_validation | 1264.3 (1724, 1409, 660) | 2 of 3 | 1388.7 (990, 1745, 1431) | 2 of 3 | lean |

Total passes: lean 11 of 15, direct 13 of 15.

Mean tokens per passing task: lean 797.5 (11 passes), direct 923.4
(13 passes). Lean used about 14 percent fewer tokens per passing
task.

Elapsed time: lean runs 1115 seconds total, direct runs 837 seconds
total, 1952 seconds for all 30 runs. Fastest single run was 9
seconds.

### Honest reading

- Lean does NOT win consistently. Lean had the lower mean token
  count on only 2 of 5 tasks (task2 and task5). Direct had the
  lower mean on tasks 1, 3, and 4.
- Lean passed less often: 11 of 15 runs, against 13 of 15 for
  direct. The improvement did not fix that.
- The one number that still favours lean is tokens per passing
  task: 797.5 against 923.4, about 14 percent fewer. It held in
  both batches (Batch 3: 560.5 against 579.75).
- The extra steps rescued 4 runs that would have failed at 3
  steps: task1 direct rep 3 passed in 4 steps, task4 direct rep 3
  passed in 5 steps, task5 lean rep 2 passed in 4 steps, task5
  direct rep 3 passed in 4 steps.
- The extra steps also made failures more expensive. All 6 failed
  runs burned the full 5 steps and between 1687 and 2652 tokens,
  and the error in every case is "Max steps reached without
  passing tests." A failed lean run can cost more than a passed
  direct run.
- The spread inside one task and mode is very large. Task4 lean
  ranged from 462 to 2652 tokens across its 3 repeats; task2
  direct ranged from 278 to 1687 tokens. With this 3b model, no
  mean here is a stable truth, it is an average of 3 noisy runs.
- Combined across both batches: lean passed 15 of 20 runs,
  direct passed 17 of 20. Combined tokens per passing task: lean
  734.3 (11015 tokens over 15 passes), direct 842.5 (14323 tokens
  over 17 passes). So lean uses about 13 percent fewer tokens per
  passing task across all measured runs, but passes less often.
- Cost is 0.0 for every run: the model runs locally, so there is
  no per-token price. No cost figure is invented.

### verify.py

`python3 verify.py` on all 40 committed traces (10 from Batch 3,
30 from Batch 4): PASS, exit 0, 4.8 seconds. 83 unit tests run,
passed. 40 of 40 traces replayed and matched (patches re-applied,
hidden tests re-run, ledger token totals checked). The failed tasks
replay as failures too, which is the point: replay checks what
happened, it does not turn failures into passes.
