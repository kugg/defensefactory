# Make the assessment disposition visible in the ticket lifecycle

Assessment evidence and native ticket state are separate records. The evidence
answers what the factory concluded and why. The native status and a single
disposition label make that conclusion visible to people working from the queue.
Do not leave a completed disposition in Backlog merely because a later factory
run might find it convenient.

## Project lifecycle policy

Discover the team's current native status and label configuration through the
ticket connector. Bind the selected mapping in a versioned project policy. The
portable helper uses four semantic state classes (`complete`, `canceled`,
`backlog`, `in_progress`) and these canonical dispositions:

| Factory disposition | Semantic state | Terminal |
| --- | --- | --- |
| `already_fixed` | `complete` | yes |
| `accepted_risk` | `canceled` | yes |
| `false_positive` | `canceled` | yes |
| `invalid_report` | `canceled` | yes |
| `owner_decision` | `backlog` | no |
| `inconclusive` | `backlog` | no |
| `active` | `in_progress` | no |

The policy maps those semantic values to the project's actual status and label
names. Status names such as `Done` are not universal. Configure the policy
through the installation/project profile or a ticket-bound resource; never infer
it from finding prose. Create missing labels only with explicit administrative
authority. A single-select disposition label group is recommended so stale and
current dispositions cannot coexist.

## Plan, apply and read back

After publishing and reading back the assessment receipt:

1. Normalize the conclusion to one canonical disposition. A hold is not enough:
   distinguish `owner_decision` from `inconclusive`.
2. Run `scripts/stage.py disposition-lifecycle-plan` (or
   `scripts/disposition-lifecycle.py plan`) with the current ticket snapshot,
   shareable assessment receipt reference and digest, project mapping, explicit
   mutation authority and plan time. Save and attach the plan.
3. If the plan is `pending`, do not mutate the ticket or describe it as closed.
   The assessment result remains valid and its missing lifecycle authority is a
   concrete next action.
4. If the plan is `ready`, use the native connector to set the desired status and
   disposition label. Remove any other label from the configured disposition
   set. The helper intentionally does not call a remote service.
5. Fetch the issue again. Normalize that response as a retrieval and run
   `disposition-lifecycle-verify` with the saved plan. Attach the readback receipt.
   A connector response from the mutation call is not the independent readback.
6. Only a `satisfied` readback makes the lifecycle transition complete. On a
   timeout or mismatch, preserve the failure, inspect remote state, and reconcile
   before retrying. Never overwrite the assessment or earlier receipts.

The verifier checks the exact ticket, fresh retrieval time, configured status,
required disposition label and absence of conflicting configured disposition
labels. It does not re-evaluate the security evidence. Terminal readback stops
the pipeline; nonterminal readback names the remaining owner or evidence action.

## Batch and bounded trials

Batch summaries must be built from freshly read ticket states after these
readbacks, not from remembered assessment prose. A bounded re-evaluation may
preserve the prior assessment research while replacing only the current stage
checkpoint; it must not erase the visible lifecycle history. Source-only
`stop_source` remains a scoped task result and does not authorize whole-ticket
status mutation.
