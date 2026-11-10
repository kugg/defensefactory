# Experiment learning record

When an experiment is requested, publish an append-only learning entry to its ticket after each stage and meaningful failure. Retain raw failure evidence before attempting recovery. An entry contains:

* Run, stage, attempt, exact subject and frozen protocol/skill/evaluator references.
* What we expected, and the evidence that would support that expectation.
* What happened: command/tool, timestamp, outcome, raw log/resource reference and checks actually executed.
* Why: observed cause, or clearly labeled hypothesis and the next discriminating check. Do not manufacture a cause from a missing log.
* Recovery or proposed procedure/control change, who owns it, and which evidence it invalidates.
* How the change will be tested, result if executed, and remaining uncertainty.
* Measurements: elapsed time, repair/retry round, human intervention, available usage/cost, missing measurements.
* Next action and explicit stopping boundary. Read back the published record before dependent work.

Preserve prior entries and failed bytes. Corrections are new entries linked to originals. Keep case facts and raw evidence in ticket resources; update generic skills only for observed reusable lessons. Same-context reconstruction is not a fresh-context test. Model/tool usage absent from the environment remains not measured, never zero.

Record missing capture as missing, not inferred: file mtime or guessed durations cannot supply execution timestamps; names added to a later report are not executed assertions. A publication acknowledgement, separately retrieved record and verified download are three distinct outcomes. Label hypothetical scope receipts and keep them out of actual authorization. Preserve adapters, command specifications, expectations and intermediate failed receipts so the next worker can reproduce the failure, not just read its summary.

## Interrupted foreground invocation

Preserve the exact producer exit code, session ID and raw invocation log. Use
`invocation-recovery` to distinguish an observed terminal provider DNS/reset error
from a security/test failure, auth failure, ambiguous session or partial capture.
The helper only advises; it does not run another process or grant tool authority.

For a retryable transport interruption, recover the SAME session and attempt with
a new invocation log. Before further mutations, freshly fetch ticket resources
and reconcile any pending PR/upload/comment effects. Resume unfinished work; do
not relabel prior checks as new executions or reset tickets. Record the original
failure and recovery as linked receipts. Limit recovery to a declared budget
(default two retries); persistent transport/auth/tool failures get a concrete
host blocker, not an unlimited retry loop. A human-approved later retry creates a
new recovery receipt rather than overwriting the exhausted one.

The foreground serial runner owns process exit/session checkpoints and usage
supplements. CLI exit zero is not factory acceptance. Each new ticket starts a
fresh session; only the interrupted ticket resumes its named existing session.
Do not retry a counterexample/test failure until green or silently replace a
frozen skill version during recovery. Generic skill fixes belong in a new
package; substantive changes to case requirements/evaluators need new evidence.

A configured MCP server can fail during tool discovery because one of its
existing dependencies is down. Record the actual server error and inspect its
own logs before guessing a source/indexing failure. A bounded, authorized local
dependency recovery must preserve stores, indexes and configuration; do not
recreate resources or invent coverage. Record the environment change separately
from frozen skill/source inputs. An already-open client may need reconnection or
a new invocation of the SAME recorded session to refresh its tool inventory.
Retain both inventories and the earlier failure. Discovery success still does
not establish indexed revision, semantic quality or coverage.

For long foreground Bash batches, snapshot the trusted runner and its explicit
input resources before launch with `scripts/frozen_runner.py`. It validates Bash
syntax, preserves a byte manifest, and optionally runs that private copy with
`--run`. This prevents later edits to a shared runner from changing shell input
mid-run; it does not authenticate the script or grant permissions. Distinguish
per-ticket producer exits from the outer wrapper exit: a final summary failure
does not require rerunning already completed cases. Reconcile their receipts.
