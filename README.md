# LeanCoder

LeanCoder is a coding agent that completes real development tasks while using the fewest tokens, and proves the saving with a measured token ledger.

## Problem

AI coding tools send the whole repository on every turn. Teams pay for context they never needed, and nobody can prove what a task actually cost. A run can also keep going after a provider outage, blow past a spending limit, leak private code to a remote model, or write files and run shell commands with no approval.

## Solution

LeanCoder sends only the code a task needs, found by a small local code search, and it re-reads files on every step so a retry sees the current file state. It asks for approval before every file write, shell command, and Git action. It enforces a per-task token budget with a hard stop. It routes every model call through Bifrost, with a local model fallback when a provider fails, and private tasks run only on a local model. Every run writes a token ledger, so lean mode versus direct mode is a measured number, not a claim.

## Architecture

- `leancoder/bifrost_client.py`: OpenAI-compatible client for a Bifrost base URL from the environment, timeout, retry once only on timeout, clear error on 401, token counting from the response usage field.
- `leancoder/budget.py`: per-task token and cost budget, hard stop when the budget is exceeded.
- `leancoder/approval.py`: approval gate before file writes, shell commands, and Git actions, default approval required, labelled `--auto-approve` demo mode only.
- `leancoder/tools.py`: sandboxed file write, shell, and Git tools, all inside the task repo only, every action logged.
- `leancoder/agent.py`: the agent loop, lean retrieval first, then model call, then tool call, then test run, with a max-steps limit.
- `leancoder/ledger.py`: token ledger, one JSON record per run under `traces/`, with model calls, tool calls, test results, approval decisions, applied patches, and task results. Cost is recorded only when known, local models cost 0, anything else is unknown, never guessed.
- `leancoder/replay.py`: replays a recorded trace offline, re-applies the patches to a fresh copy of the starter code, runs the hidden tests, and checks the ledger numbers match. Differences are reported plainly, never silently fixed.
- `verify.py`: the judge verification path, offline, no key, no Docker, no Bifrost. Runs the full unit test suite, replays the recorded traces, and prints PASS or FAIL with the measured numbers.
- `tasks/`: 5 small real dev tasks, each with a task description, a starter repo, and hidden tests that grade pass or fail.
- `tests/`: unit tests with mocked HTTP and mocked model calls, no live call, no real key.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your own values. Never commit `.env`. Never put a key in code.

## Run

Judge verification, offline, no key, no Bifrost, no Docker, under
2 minutes, and under 5 minutes including the unit tests:

```bash
python3 verify.py
```

This runs the full unit test suite, replays every recorded trace
in the committed example trace sets
(`examples/measured-traces/` and `examples/measured-traces-batch4/`),
re-applies the patches, runs the hidden tests, and
checks the ledger numbers. It prints PASS or FAIL with the measured
numbers, and exits 0 only when everything passes. Pass
`--traces-dir` to replay a different directory instead.

Unit tests alone, offline:

```bash
python3 -m unittest discover -s tests -v
```

Replay one recorded run by hand:

```bash
python3 -c "from leancoder.replay import replay_ledger, replay_summary_text; print(replay_summary_text(replay_ledger('traces/run-20261109-000000.json')))"
```

Live run (needs Bifrost running and a model configured in Bifrost):

```bash
export BIFROST_BASE_URL=http://localhost:8080
export BIFROST_API_KEY=your-key-here
python3 -m leancoder.agent --task task1_add_function --mode lean --model gemini/gemini-2.5-flash
```

Run Bifrost first, for example with Docker:

```bash
docker run -p 8080:8080 maximhq/bifrost
```

Bifrost dashboard: http://localhost:8080

## Modes

- Lean mode: send only the files the task needs, found by local code search.
- Direct mode: send the whole repo context on every model call. This is the naive baseline.
- The headline number is tokens per passing task in lean mode versus direct mode, measured on the same 5 tasks.

## Measured results

Live runs are done and recorded in [MEASURED.md](MEASURED.md), with
the 10 Batch 3 ledger traces committed in
`examples/measured-traces/` and the 30 Batch 4 traces in
`examples/measured-traces-batch4/`, all replayed by `verify.py`.

Batch 3 headline, measured on 2026-11-08 with
ollama/qwen2.5-coder:3b through Bifrost v2.5.0, one run per task per
mode: lean mode 3344 tokens total, 4 of 5 tasks passed; direct mode
3810 tokens total, 4 of 5 passed. Tokens per passing task: lean
560.5, direct 579.75.

Batch 4 headline, measured on 2026-11-08 with the same model, 3
repeats per task per mode, agent max steps raised from 3 to 5:
lean mode 11 of 15 runs passed, direct mode 13 of 15. Mean tokens
per passing task: lean 797.5, direct 923.4. Lean had the lower mean
token count on only 2 of 5 tasks, so lean does NOT win
consistently. What the numbers do support: lean used fewer tokens
per passing task in both batches, 734.3 against 842.5 combined
across all 40 runs, about 13 percent fewer, but passed less often,
15 of 20 against 17 of 20. Both batches failed some tasks, and the
failures are shown as failures in MEASURED.md, not hidden.

## How AI is used

The agent uses a language model through Bifrost to read task descriptions, propose patches, and fix failing tests. The model never writes a file directly. Every patch goes through the approval gate, every run is bounded by a token budget, and every token is counted from the model response usage field. Private tasks run only on a local Ollama model, never on a remote free tier model.

## Limits

- A live agent run from zero is NOT under 5 minutes, because it needs Bifrost and Ollama running and a model downloaded. The under-5-minute judge path is `python3 verify.py` plus the unit tests, all offline, which replays the recorded runs instead of making a live model call.
- Live runs are done, but only with one local model, ollama/qwen2.5-coder:3b. No remote model was run, because no provider key is on file. Every model call reads its key from the environment only, and every unit test uses mocked HTTP, so the unit tests prove nothing live. The measured live runs are the 40 traces in `examples/measured-traces/` and `examples/measured-traces-batch4/`, described in MEASURED.md.
- A live agent run needs Bifrost running and a model configured in Bifrost. The offline verify path replays recorded traces and runs the unit tests, it does not make a live model call.
- Free tier rate limits apply to the free tier model, check the live numbers in Google AI Studio.
- Run ledgers live under `traces/`, which is gitignored, so day-to-day run records are never committed. The 40 verified measured traces are the exception: they are copied to `examples/measured-traces/` and `examples/measured-traces-batch4/` and committed as proof. Cost is shown only where it is known, local models cost 0, and anything else is recorded as unknown, never guessed.
- The 3b model is small and inconsistent: the same task in the same mode gave different results on repeat runs. Batch 3 numbers are one measured run per task per mode; Batch 4 numbers are means of 3 repeats per task per mode, and the spread inside one task and mode is very large (task4 lean ranged from 462 to 2652 tokens).
