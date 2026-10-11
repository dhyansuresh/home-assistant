# Dedicated vision model with an LLM coordinator

## Decision and implementation status

The project owner selected this method on 2026-10-10 (D-014): a dedicated Hugging Face vision model supplies visual evidence, and one LLM coordinates recognition tools. Use an OpenAI LLM and a fine-tuned Hugging Face vision model for P0 (D-018). Start with one vision tool. Additional specialist tools or autonomous agents are extensions after the core flow works.

The internal SigLIP2 gallery recognizer, `/internal/recognize` endpoint, FastAPI `VisionServiceProvider`, and orchestrator image handoff are implemented. The service returns registered-product candidates or unknown; it is not a general image captioner or an image-safety classifier. Wake detection, speech-to-text, task sessions, the full recognition coordinator, OCR, and product catalog beyond the configured gallery remain unimplemented. D-015 adds required voice-led continuous capture; see [VOICE_CAPTURE.md](VOICE_CAPTURE.md).

## Why separate recognition from reasoning?

The main reason is specialization and control. A dedicated vision model can be trained and evaluated on the team's grocery products and webcam conditions. The LLM coordinates tool use and handles uncertainty. Each component can be changed and measured independently.

This also allows the team to choose recognition model size and GPU deployment independently of the LLM provider. It does not prove that the design is faster, cheaper, or more accurate. A multimodal LLM could perform recognition directly and is a legitimate comparison when time and access permit.

Suggested explanation for judges:

> We separate visual recognition from reasoning. A dedicated vision model identifies candidate products, while the LLM coordinates tools and handles ambiguity. This lets us train, test, and improve recognition independently. We measure accuracy, response time, and cost before claiming an advantage over a multimodal LLM.

## Roles and flow

| Component | Responsibility | Stage |
| --- | --- | --- |
| Fine-tuned SigLIP2 or ViT | Return ranked product candidates or unknown from a still image. | P0 |
| OpenAI LLM coordinator | Combine the full active conversation, finalized speech with visual evidence, clarify a task, and request confirmation. Accept visual evidence or abstain. Mutation tools become available only after confirmation and collection stop. | P0 |
| Wake detector and speech-to-text | Detect "Hey HomePilot" while armed; transcribe the task during continuous capture. Provider and placement remain open. | P0 |
| FastAPI adapter | Validate uploads, execute allowed calls, enforce limits, validate results, and serve the existing response shape. | P0 |
| User confirmation UI | Offer candidate review, correction, retake, and manual entry before saving. | P0 |
| Label/OCR tool | Extract visible brand, name, or size as additional evidence. | Optional P1 |
| Product catalog lookup | Resolve evidence against an explicit catalog; inventory alone is not a product catalog. | Optional P1; schema/data source still to be designed |
| Independently planning specialist agents | Choose their own tools or retries for a demonstrated need. | Optional P1; not required for baseline |

After "Hey HomePilot", the browser keeps the webcam active and captures fresh frames throughout task collection, sending sampled images through FastAPI alongside finalized transcript updates. The separate mobile point-and-click mode captures exactly one image per tap without voice activation and is also P0. Each stationary recognition call accepts one sampled image; repeated captures belong only to the active stationary session. The coordinator calls the vision tool through FastAPI; inference runs in the AMD ROCm vision service. The coordinator consumes structured candidates, scores, and unknown status. A text-only LLM is sufficient for this interface; an LLM that inspects the image itself must be multimodal.

The task draft and visual result go through backend validation to the confirmation UI. Once the understood task is explicitly confirmed, task capture/transcription stop before execution. Confirmed scanned additions, list/quantity changes, and household reads use allowlisted runtime MCP tools executed by the backend. The inventory-addition tool records history for last-added queries. Named-item/list/history requests can use MCP without invoking vision. The collecting/clarifying phase never invokes mutation tools. Developer GitHub MCP is only for coding agents and is never available to the application coordinator.

## Bounded first implementation

These are implementation defaults for the first integration, to be recorded with actual tested limits in its PR:

- Continuous capture supplies fresh frames over the active task session. Use bounded frame sampling, at most one in-flight inference per session, and latest-frame replacement rather than an unbounded queue. Do not repeatedly infer the same frame. Enforce finite session duration, inference/turn budgets, and timeouts; the starting limits in `VOICE_CAPTURE.md` are proposals to measure.
- Pass a request-scoped image reference to the adapter. The model cannot select arbitrary files or URLs.
- Preserve candidate fields, scores, order, and vision checkpoint ID when accepting the result. The coordinator may abstain, but cannot invent a product, add a brand/size, manufacture a score, or override unknown without evidence.
- For each frame result, preserve `unknown: true` with an empty candidate list on abstention. The session may request a clearer view or manual identification through its new clarification contract. Do not treat an older known frame as proof of the object now being discussed.
- Treat raw vision scores as ranking signals, not calibrated confidence percentages. Do not average scores from different models without a validated method.
- Return a dependency error on timeout, malformed tool output, or unavailable inference/LLM. Unknown means identification was attempted without sufficient evidence; it is not a substitute for an operational error.
- Record request ID, actual model versions, tool outcomes, timing, and LLM usage for evaluation. Do not log secrets or household image contents by default.

One coordinator with one tool offers limited adaptive behavior. Its P0 role includes coordinating spoken intent, fresh visual evidence, clarification, and task confirmation. Additional sources such as label text may make coordination more useful, but should be added only with a clear issue and evaluation evidence. Do not describe multiple tool calls as multiple autonomous agents.

## Evaluation and delivery order

1. Developer 1 establishes direct vision inference on the actual AMD GPU and records GPU, ROCm/PyTorch versions, checkpoint, preprocessing, and supported product vocabulary. A Hugging Face checkpoint is not by itself proof of compatibility with the allocated GPU environment.
2. Developers 1 and 4 assemble a held-out webcam set with known products, visually similar packaging, unknown products, blur, and lighting variation. Keep evaluation images separate from training and threshold tuning.
3. Developer 1 fine-tunes the selected vision model on a documented product dataset and evaluates the saved checkpoint against the baseline; fine-tuning is required P0. Developers 2 and 3 add the OpenAI coordinator adapter and enforce result validation and call limits. Use the same held-out images to compare the base and fine-tuned checkpoints. When measuring the effect of orchestration separately, keep the vision checkpoint fixed.
4. Report top-1/top-3 where relevant, wrong identifications, unknown/abstention rate, and correctness among accepted results. Include per-stage and end-to-end latency, tool-call count, and LLM token usage/cost. An increase in abstentions alone is not improved recognition accuracy.
5. If feasible, evaluate a direct multimodal LLM on the same images and product-identification criteria. Label this comparison untested until it is actually run. Report limitations and sample size rather than promising a performance advantage.
6. Complete the desktop wake → continuous capture/transcription → clarification → confirmation → stop collection → execute flow before P0. Evaluate wake misses/false triggers, transcript/task correctness, frame freshness, stop behavior, and execution deduplication alongside model metrics. Complete stationary voice on laptop/iPhone and separate iPhone point-and-click within P0. Add one complementary tool at a time and repeat the evaluation before adding independently planning agents.

No numerical accuracy target, cost saving, or latency improvement has been established. Owners should agree acceptance thresholds and record measured results in the implementation PR. If coordination adds overhead without useful behavior, bring that evidence to the team for a scope decision.

## Tool execution and conversation context

OpenAI selects a tool call; application code executes it and returns the result to the model. FastAPI supplies the validated captured image to the Hugging Face model service. A model hosted on Hugging Face is not required: the checkpoint can be served on the team's AMD ROCm GPU. The OpenAI model can operate on transcript and structured tool evidence without inspecting the image itself. [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)

Keep the original user request, subsequent answers, assistant clarification, corrections, and tool outcomes in the active conversation. For example, "add this", followed by "to inventory" and "two", is one evolving task. Maintain context until the task is resolved; expire it explicitly rather than silently dropping the initial intent. Persistent cross-session conversation memory is not required. Database history is retrieved through MCP and is independent of conversational memory.

## Primary references

- [Hugging Face SigLIP2](https://huggingface.co/docs/transformers/model_doc/siglip2): vision-language encoders, candidate-label classification, and retrieval.
- [Hugging Face image classification](https://huggingface.co/docs/transformers/tasks/image_classification): fine-tuning and evaluating a ViT classifier.
- [Hugging Face multi-agent orchestration](https://huggingface.co/docs/smolagents/examples/multiagents): optional manager/specialist pattern; no framework dependency is selected for this project.
