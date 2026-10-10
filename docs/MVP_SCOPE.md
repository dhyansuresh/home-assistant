# MVP scope and exit gate

## P0: required software flow

| Capability | Exit evidence |
| --- | --- |
<<<<<<< Updated upstream
| Desktop webcam capture | A desktop browser can start a built-in or USB webcam, preview it, capture a still image, and stop the camera. Permission errors are actionable and image-file selection is available as a fallback. |
| Product recognition | AMD ROCm-hosted service returns ranked candidates or `unknown` using a recorded Hugging Face SigLIP2/ViT baseline. Test on fresh photos. |
| Confirmation | User can accept or edit name and quantity; no scanned item is saved without explicit confirmation. |
| Inventory | Confirmed item is persisted in Supabase and is visible after reload. |
| Text assistant | A user request reaches one chosen LLM provider, invokes an allowlisted Python runtime MCP tool, and reports the tool result. |
| Grocery list | Assistant can read inventory and add an item to a persisted list; UI shows the updated list. |
| End-to-end demo | A teammate can run the demo story in `PRODUCT.md` from a desktop webcam without developer intervention between steps. |
=======
| Enable listening and wake activation | User enables listening and grants microphone/camera permissions in tested laptop and iPhone browsers with the app visible. Saying "Hey HomePilot" starts one task session and activates the webcam. Before wake, the camera is off. UI clearly shows listening/capture state. |
| Mobile point-and-click | A separate phone/iPhone captures one image per tap without wake activation or microphone permission. It uses the same household backend and confirmed-action flow outside the stationary camera range. |
| Continuous webcam capture | Camera stays active during task collection and supplies fresh frames throughout it, with bounded sampling/inference and no unbounded queue. Manual capture and file selection remain fallbacks. |
| Speech-to-text | Spoken task and clarification answers appear as a live transcript. Final segments update the task draft; partial text never triggers actions. Handle pauses, corrected transcripts, and recognition failure. |
| Product recognition | AMD ROCm-hosted service returns ranked candidates or unknown using a fine-tuned Hugging Face SigLIP2/ViT checkpoint, with training provenance and held-out evaluation against the baseline. Correlate each result to the correct session/frame. Test on fresh photos. |
| LLM coordinator | Gemini uses the full active conversation, final transcript revisions, and relevant visual evidence to understand a supported task, asks for missing details, and presents the task for confirmation. Preserve evidence and unknown handling; compare with the direct vision baseline. |
| Confirm, stop, then execute | User confirms the understood task by voice or button. Camera capture and task transcription stop before execution begins. Silence or wake detection alone never confirms a task. A late frame/transcript cannot modify the confirmed task. |
| Inventory | A scanned item and quantity are explicitly confirmed, saved through runtime MCP with an inventory-addition event, and visible after reload. An explicit task confirmation containing those details may also serve as item confirmation. |
| Assistant and grocery list | A confirmed spoken task reaches an allowlisted Python runtime MCP tool and updates the persisted list exactly once; show its actual outcome. Typed chat remains available. |
| Read and history requests | Voice can show the complete grocery list and report the last recorded addition of rice. History comes from persisted inventory-addition events, with explicit no-history and ambiguous-item handling. Named-item and read requests work without a recognized product in view. |
| Conversation continuity | Preserve all active-session turns and corrections, including words spoken immediately after the wake phrase. A follow-up answer must be interpreted in the context of the original request. |
| Stop and recovery | Stop/Cancel, permission loss, timeout, tab hiding, or dependency failure ends collection without executing an unconfirmed task. Clearly report failures; permit retry or manual input. Disable listening releases microphone and camera. |
| End-to-end demo | A teammate can run the stationary laptop/iPhone voice stories and separate mobile one-photo story in PRODUCT.md. Both modes use the same household data; neither mode alone passes P0. |
>>>>>>> Stashed changes

The team should record the model checkpoint, test set, top-1/top-3 results where relevant, unknown cases, and inference latency. Similarity scores must not be presented as calibrated confidence percentages.

## P1: only after P0 is stable

**First: iPhone capture and responsive workflow**, reusing the same upload endpoint after the desktop demo passes. Then consider fine-tuning, barcode/OCR fallback, richer quantity actions, stock-based suggestions, voice in the web app, and visual polish. Each needs an issue that explains how it improves the tested flow.

## P2: post-MVP hardware

Raspberry Pi Zero 2 W and its Logitech Brio camera/microphone integration, KLYSTR SPI LCD, speaker/audio, USB/power work, and a 3D printed enclosure. Begin this track only after every P0 row above is demonstrated. A Brio attached to a development computer is already allowed for P0. The robot must reuse the existing application API; it must not block the software release.

## Explicitly out of the MVP

Real grocery checkout, payment, ordering, autonomous purchasing, continuous video inference or recording (local webcam preview is allowed), wake word, general smart-home control, multi-household account management, and production public access. The current foundation has no authentication; use a private, single-household demo environment until access control is designed and implemented.
