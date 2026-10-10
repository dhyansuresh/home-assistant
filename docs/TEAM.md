# Four-person ownership and handoffs

Assign names to these roles in the team's first issue or project board. Ownership means primary responsibility and review, not exclusive edit rights.

| Developer | Owns | First deliverable | Needs from others |
| --- | --- | --- | --- |
| 1 — ML/vision | `services/vision`, model evaluation, AMD ROCm setup | Fine-tuned checkpoint, training record and baseline comparison; real frame inference and safe sampling budget | Session/frame contract with 2; fresh-frame test cases with 4 |
| 2 — Backend/data/integration | `services/api`, `supabase`, `contracts` coordination | Reviewed voice-session contract and lifecycle, confirmation gate, deduplicated execution, persisted routes | Frame outputs from 1; task/STT needs from 3; media lifecycle from 4 |
| 3 — Agent/runtime MCP | `services/runtime_mcp`, LLM coordinator with 2; wake/STT selection with 4 | Final transcript + visual evidence → task draft/clarification → explicit confirmation; validated MCP action | Evidence from 1, session/DB adapter from 2, transcript and confirm events from 4 |
| 4 — Frontend/product | `apps/web`, stationary laptop/iPhone voice and separate mobile point-and-click | Enable listening, wake activation, continuous frames/STT, transcript and task confirmation, stop acknowledgement, manual fallbacks | Voice/session contract from 2, wake/STT adapter from 3, frame budget from 1 |

## Dependency order

At hour zero, agree on product fields, units, unknown response, confirmation, and error shape in `contracts/openapi.yaml`. Developer 2 opens this PR; all four review it. Then each owner works with contract fixtures while live services are built. Build image and typed-action baselines, then integrate wake detection, continuous capture/STT, task interpretation, clarification/confirmation, collection-stop acknowledgement, and execution. Stationary voice on laptop/iPhone, separate mobile point-and-click, fine-tuned inference, full conversation context, and last-added history must all pass P0. Desktop-first only describes implementation order. Shared changes require a PR with affected owners tagged for review.

## Suggested issues

1. **Voice and data contracts** (2; review 1/3/4): define session events, media/transcript correlation, task revisions, confirmation/stop gate, cancellation and execution deduplication; review migration.
2. **Vision baseline and frame budget** (1; depends on contract): verify GPU, serve candidates/unknown, measure latency and bounded sampling; fine-tune and evaluate the saved checkpoint before P0.
3. **Inventory API** (2; depends on migration): route confirmed additions through MCP with atomic addition events and retry deduplication; support both capture modes.
4. **Runtime MCP tools** (3; depends on migration): read inventory/list, add identified items, retrieve last-added events, and apply validated actions with truthful errors.
5. **Typed agent baseline** (3 + 2; depends on tools): OpenAI and allowlisted actions; no partial voice transcription is routed here.
6. **Wake and speech spike** (4 + 3; early): demonstrate the exact phrase on the demo browser, permissions, STT pauses and final segments, provider failure, and media stop. Record implementation choices.
7. **Task-session backend** (2 + 3; depends on 1): draft/clarify/confirm, stop acknowledgement, cancel/expiry, stale events, exactly-once effect under retries.
8. **Continuous capture UI** (4; depends on 1/6): camera stays active during collection; sample fresh frames with backpressure; show transcript/clarification/confirmation; stop task media and acknowledge before execution.
9. **Voice/vision coordinator** (3 + 2; depends on 2/7/8): preserve the full conversation and combine final utterances with relevant frame evidence, ask for missing fields, and freeze confirmed task revisions. Developer 1 evaluates evidence accuracy.
10. **End-to-end voice rehearsal** (all; depends on 2–9): wake → spoken task with frames → clarification → confirmation → stop capture/transcription → one persisted action. Cover VOICE_CAPTURE.md failure cases.
11. **iPhone modes — P0** (4 + 1/2/3): validate stationary wake/conversation and separate one-photo capture with no voice requirement on an actual iPhone; verify both clients use the same household data.
12. **Inventory-addition history — P0** (2 + 3): migration and atomic event write, latest matching event lookup, no-history/ambiguity, and duplicate protection; demonstrate the rice question.

## Review and validation

- A PR touching `contracts/openapi.yaml` needs all affected consumers and producers to review it. Include before/after payload examples.
- A PR touching `supabase/migrations` needs Backend and Agent review, plus a migration result against a disposable Supabase project.
- A PR touching user flow needs desktop browser repro notes; add iPhone evidence when changing the phone workflow; model behavior changes need fresh-photo examples and unknown cases.
- Validate YAML/JSON syntax, Python import/compile, and TypeScript build for changed areas. Run an end-to-end desktop webcam test before calling P0 complete. Verify microphone/camera denial, false/repeated wake, no device, silence, interim corrections, unknown/conflicting frames, retake, and camera/task-STT release before execution. Also verify cancellation, hidden tab, timeout, late callbacks, and duplicate confirmation/retry cannot cause duplicate writes; use `VOICE_CAPTURE.md` acceptance scenarios. Run iPhone stationary and mobile-capture checks as P0 gates; verify the three named voice examples and shared history/list state. Record exact commands and outcomes in PRs.
- Keep `main` demoable; avoid merging a mocked flow as if it were live.
