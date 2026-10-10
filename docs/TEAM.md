# Four-person ownership and handoffs

Assign names to these roles in the team's first issue or project board. Ownership means primary responsibility and review, not exclusive edit rights.

| Developer | Owns | First deliverable | Needs from others |
| --- | --- | --- | --- |
| 1 — ML/vision | `services/vision`, model evaluation, AMD ROCm setup | Real `/internal/recognize` response including unknown case | Contract review with 2; test images and candidate vocabulary with 4 |
| 2 — Backend/data/integration | `services/api`, `supabase`, `contracts` coordination | Reviewed OpenAPI + migration; persisted inventory routes | Vision response from 1; tool requirements from 3; UI feedback from 4 |
| 3 — Agent/runtime MCP | `services/runtime_mcp`, LLM path | MCP inventory/list tools and one traced successful write | DB access pattern from 2; tool shapes in contract; UI chat request from 4 |
| 4 — Frontend/product | `apps/web`, desktop webcam first, iPhone next | Webcam preview/snapshot, editable confirmation, inventory/list/chat views | API examples from 2; model uncertainty behavior from 1 |

## Dependency order

At hour zero, agree on product fields, units, unknown response, confirmation, and error shape in `contracts/openapi.yaml`. Developer 2 opens this PR; all four review it. Then each owner works with contract fixtures while live services are built. Integrate the webcam snapshot path first, inventory persistence second, MCP action third, and the full desktop demo next. Then adapt and test the iPhone capture path. Shared changes require a PR with affected owners tagged for review.

## Suggested issues

<<<<<<< Updated upstream
1. **Contract and database** (2; review 1/3/4): agree payloads and apply migration.
2. **Vision baseline** (1; depends on contract): verify GPU, serve real candidate/unknown response, report evaluation.
3. **Inventory API** (2; depends on migration): validate confirmation and persist/retrieve items.
4. **Runtime MCP tools** (3; depends on migration): list inventory, add/read grocery items, handle errors.
5. **Agent chat** (3 + 2; depends on tools): one LLM provider, allowlisted calls, truthful responses.
6. **Desktop UI** (4; depends on contract): webcam start/stop, snapshot/preview, file fallback, edit and confirm, list and chat views.
7. **End-to-end rehearsal** (all; depends on 2–6): webcam snapshot to saved item and chat to persisted list.
8. **iPhone capture** (4 + 1; after desktop rehearsal): adapt the same UI/endpoint and evaluate recognition on fresh phone images.
=======
1. **Voice and data contracts** (2; review 1/3/4): define session events, media/transcript correlation, task revisions, confirmation/stop gate, cancellation and execution deduplication; review migration.
2. **Vision baseline and frame budget** (1; depends on contract): verify GPU, serve candidates/unknown, measure latency and bounded sampling; fine-tune and evaluate the saved checkpoint before P0.
3. **Inventory API** (2; depends on migration): route confirmed additions through MCP with atomic addition events and retry deduplication; support both capture modes.
4. **Runtime MCP tools** (3; depends on migration): read inventory/list, add identified items, retrieve last-added events, and apply validated actions with truthful errors.
5. **Typed agent baseline** (3 + 2; depends on tools): Gemini and allowlisted actions; no partial voice transcription is routed here.
6. **Wake and speech spike** (4 + 3; early): demonstrate the exact phrase on the demo browser, permissions, STT pauses and final segments, provider failure, and media stop. Record implementation choices.
7. **Task-session backend** (2 + 3; depends on 1): draft/clarify/confirm, stop acknowledgement, cancel/expiry, stale events, exactly-once effect under retries.
8. **Continuous capture UI** (4; depends on 1/6): camera stays active during collection; sample fresh frames with backpressure; show transcript/clarification/confirmation; stop task media and acknowledge before execution.
9. **Voice/vision coordinator** (3 + 2; depends on 2/7/8): preserve the full conversation and combine final utterances with relevant frame evidence, ask for missing fields, and freeze confirmed task revisions. Developer 1 evaluates evidence accuracy.
10. **End-to-end voice rehearsal** (all; depends on 2–9): wake → spoken task with frames → clarification → confirmation → stop capture/transcription → one persisted action. Cover VOICE_CAPTURE.md failure cases.
11. **iPhone modes — P0** (4 + 1/2/3): validate stationary wake/conversation and separate one-photo capture with no voice requirement on an actual iPhone; verify both clients use the same household data.
12. **Inventory-addition history — P0** (2 + 3): migration and atomic event write, latest matching event lookup, no-history/ambiguity, and duplicate protection; demonstrate the rice question.
>>>>>>> Stashed changes

## Review and validation

- A PR touching `contracts/openapi.yaml` needs all affected consumers and producers to review it. Include before/after payload examples.
- A PR touching `supabase/migrations` needs Backend and Agent review, plus a migration result against a disposable Supabase project.
- A PR touching user flow needs desktop browser repro notes; add iPhone evidence when changing the phone workflow; model behavior changes need fresh-photo examples and unknown cases.
- Validate YAML/JSON syntax, Python import/compile, and TypeScript build for changed areas. Run an end-to-end desktop webcam test before calling P0 complete. Verify denied permission, no webcam, retake, and camera release after Stop or leaving the page. Run iPhone checks for the follow-up capture milestone. Record exact commands and outcomes in PRs.
- Keep `main` demoable; avoid merging a mocked flow as if it were live.
