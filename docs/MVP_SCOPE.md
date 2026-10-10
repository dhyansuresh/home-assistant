# MVP scope and exit gate

## P0: required software flow

| Capability | Exit evidence |
| --- | --- |
| Enable listening and wake activation | User enables listening and grants microphone/camera permissions in tested laptop and iPhone browsers with the app visible. Saying "Hey HomePilot" starts one task session and activates the webcam. Before wake, the camera is off. UI clearly shows listening/capture state. |
| Mobile point-and-click | A separate phone/iPhone captures one image per tap without wake activation or microphone permission. It uses the same household backend and confirmed-action flow outside the stationary camera range. |
| Continuous webcam capture | Camera stays active during task collection and supplies fresh frames throughout it, with bounded sampling/inference and no unbounded queue. Manual capture and file selection remain fallbacks. |
| Speech-to-text | Spoken task and clarification answers appear as a live transcript. Final segments update the task draft; partial text never triggers actions. Handle pauses, corrected transcripts, and recognition failure. |
| Product recognition | AMD ROCm-hosted service returns ranked candidates or unknown using a fine-tuned Hugging Face SigLIP2/ViT checkpoint, with training provenance and held-out evaluation against the baseline. Correlate each result to the correct session/frame. Test on fresh photos. |
| LLM coordinator | OpenAI uses the full active conversation, final transcript revisions, and relevant visual evidence to understand a supported task, asks for missing details, and presents the task for confirmation. Preserve evidence and unknown handling; compare with the direct vision baseline. |
| Confirm, stop, then execute | User confirms the understood task by voice or button. Camera capture and task transcription stop before execution begins. Silence or wake detection alone never confirms a task. A late frame/transcript cannot modify the confirmed task. |
| Inventory | A scanned item and quantity are explicitly confirmed, saved through runtime MCP with an inventory-addition event, and visible after reload. An explicit task confirmation containing those details may also serve as item confirmation. |
| Assistant and grocery list | A confirmed spoken task reaches an allowlisted Python runtime MCP tool and updates the persisted list exactly once; show its actual outcome. Typed chat remains available. |
| Read and history requests | Voice can show the complete grocery list and report the last recorded addition of rice. History comes from persisted inventory-addition events, with explicit no-history and ambiguous-item handling. Named-item and read requests work without a recognized product in view. |
| Conversation continuity | Preserve all active-session turns and corrections, including words spoken immediately after the wake phrase. A follow-up answer must be interpreted in the context of the original request. |
| Stop and recovery | Stop/Cancel, permission loss, timeout, tab hiding, or dependency failure ends collection without executing an unconfirmed task. Clearly report failures; permit retry or manual input. Disable listening releases microphone and camera. |
| End-to-end demo | A teammate can run the stationary laptop/iPhone voice stories and separate mobile one-photo story in PRODUCT.md. Both modes use the same household data; neither mode alone passes P0. |

The owner confirmed that capture ends when the task is understood and confirmed, before execution finishes (D-015). [VOICE_CAPTURE.md](VOICE_CAPTURE.md) defines the lifecycle and acceptance scenarios. The existing scaffold implements only manual local webcam preview/snapshot; the new voice/session flow is required work.

Record model checkpoint, held-out test set, top-1/top-3 where relevant, wrong identifications, unknown/abstention rate, stage/end-to-end latency, tool-call count, and LLM usage/cost. Include wake misses/false activations, task/transcript correctness, and proof that confirmed tasks execute once after collection stops. Scores are not calibrated confidence percentages. See [RECOGNITION_DESIGN.md](RECOGNITION_DESIGN.md).

## P1: only after P0 is stable

Consider barcode/OCR, product catalog lookup, independently planning specialist agents where evaluation justifies them, richer quantity actions, stock-based suggestions, spoken assistant replies, and visual polish. Laptop/iPhone stationary voice, mobile point-and-click, conversation continuity, and model fine-tuning are P0.

## P2: post-MVP hardware

Raspberry Pi Zero 2 W and its Logitech Brio integration, KLYSTR SPI LCD, robot microphone/speaker, USB/power work, and a 3D printed enclosure. Start only after every P0 row passes. A webcam and microphone attached to a development computer are required P0 inputs. The robot must reuse the application API.

## Explicitly out of the MVP

Real grocery checkout, payment, autonomous purchasing, permanent audio/video recording, unrestricted inference on every video frame, system-wide wake listening with the browser closed, general smart-home control, multi-household accounts, and production public access. Active-session continuous capture with bounded frame sampling is in scope. The current foundation has no authentication; use the private single-household demo boundary until access control is implemented.
