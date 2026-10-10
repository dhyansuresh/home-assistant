# MVP scope and exit gate

## P0: required software flow

| Capability | Exit evidence |
| --- | --- |
| Desktop webcam capture | A desktop browser can start a built-in or USB webcam, preview it, capture a still image, and stop the camera. Permission errors are actionable and image-file selection is available as a fallback. |
| Product recognition | AMD ROCm-hosted service returns ranked candidates or `unknown` using a recorded Hugging Face SigLIP2/ViT baseline. Test on fresh photos. |
| Confirmation | User can accept or edit name and quantity; no scanned item is saved without explicit confirmation. |
| Inventory | Confirmed item is persisted in Supabase and is visible after reload. |
| Text assistant | A user request reaches one chosen LLM provider, invokes an allowlisted Python runtime MCP tool, and reports the tool result. |
| Grocery list | Assistant can read inventory and add an item to a persisted list; UI shows the updated list. |
| End-to-end demo | A teammate can run the demo story in `PRODUCT.md` from a desktop webcam without developer intervention between steps. |

The team should record the model checkpoint, test set, top-1/top-3 results where relevant, unknown cases, and inference latency. Similarity scores must not be presented as calibrated confidence percentages.

## P1: only after P0 is stable

**First: iPhone capture and responsive workflow**, reusing the same upload endpoint after the desktop demo passes. Then consider fine-tuning, barcode/OCR fallback, richer quantity actions, stock-based suggestions, voice in the web app, and visual polish. Each needs an issue that explains how it improves the tested flow.

## P2: post-MVP hardware

Raspberry Pi Zero 2 W and its Logitech Brio camera/microphone integration, KLYSTR SPI LCD, speaker/audio, USB/power work, and a 3D printed enclosure. Begin this track only after every P0 row above is demonstrated. A Brio attached to a development computer is already allowed for P0. The robot must reuse the existing application API; it must not block the software release.

## Explicitly out of the MVP

Real grocery checkout, payment, ordering, autonomous purchasing, continuous video inference or recording (local webcam preview is allowed), wake word, general smart-home control, multi-household account management, and production public access. The current foundation has no authentication; use a private, single-household demo environment until access control is designed and implemented.
