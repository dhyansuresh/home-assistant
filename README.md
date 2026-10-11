# HomePilot

HomePilot is a friendly grocery assistant that runs on your own computer. Say **"Hey HomePilot"**, hold a product up to
your webcam, and ask it to **add it to your grocery list**. Or just type or say **"show my grocery list"** or **"add 3
bananas"**. A pair of cartoon eyes listens, thinks and reacts; when there's something to show, HomePilot turns into a
little two-legged buddy that walks along the bottom of the screen.

Everything except voice transcription runs locally: the AI "brain" (a local language model), the product-recognition
model and your grocery list all stay on your machine.

## What it can do

- **Add items by name:** "add 2 cartons of milk", "add some eggs".
- **Show your list:** "show my grocery list".
- **Recognize products from a photo:** hold an item up (or choose a photo) and ask "what is this?" or "add this to my
  grocery list". HomePilot names the best match and **asks before saving**: *"This looks like M&M's Peanut. Should I add
  1 to your grocery list?"* Answer **yes** or **no**.
- **Admit when it doesn't know:** products it hasn't been taught come back as unknown, and it asks you to name them
  instead of guessing.
- **Stay on topic:** requests that aren't about groceries are politely declined.

It only recognizes products that have been registered in its **gallery** (photos you provide; see
[Teach it your products](#teach-it-your-products)).

## How it works

![HomePilot MVP process: stationary voice or mobile photo, LLM coordination, optional vision recognition, task confirmation, and MCP database actions.](docs/assets/homepilot-process.png)

[Open full-size diagram](docs/assets/homepilot-process.png) · [Editable SVG](docs/assets/homepilot-process.svg)

Your words (and optional photo) go to the HomePilot API. A photo is first sent to the recognition model, which returns
its best product matches or "unknown". The language model then decides what you asked for and uses the grocery-list
tools to read or update your list. The diagram shows the planned design; today the "brain" is a local
[Ollama](https://ollama.com) model (`qwen3`) rather than a cloud LLM, and the list is stored in a local SQLite file.

| Part | What it is | Runs on |
| --- | --- | --- |
| Web app (`apps/web`) | The eyes, voice and camera UI | `http://localhost:3000` |
| API (`services/api`) | Understands requests and manages the grocery list | `localhost:8000` |
| Vision service (`services/vision`) | Recognizes registered products in photos | `localhost:8001` |
| Ollama + qwen3 | The local language model | `localhost:11434` |
| ElevenLabs | Speech-to-text for voice commands (cloud, optional) | internet |

## Requirements

- A **Mac with Apple Silicon** (M1 or newer) and **macOS** (Linux also works; Windows needs WSL).
- **Memory:** 16 GB or more → use `qwen3:8b`; **8 GB** → use `qwen3:4b`.
- About **10 GB free disk** (language model 2.5–5 GB, recognition model about 1.5 GB, packages).
- [Homebrew](https://brew.sh), **Python 3.11+**, **Node.js 20.9+**, and **git**.
- A webcam and microphone (built-in is fine). Voice also needs an internet connection and an
  [ElevenLabs](https://elevenlabs.io) API key; without one you can still type and use photos.

## Setup (one time, about 20 minutes)

**1. Get the code**

```bash
git clone https://github.com/dhyansuresh/home-assistant.git
cd home-assistant
```

**2. Install Ollama and a language model**

```bash
brew install ollama
brew services start ollama
ollama pull qwen3:8b        # on an 8 GB Mac use: ollama pull qwen3:4b
```

**3. Install the Python packages** (from the repository root)

```bash
python3 -m venv .venv
.venv/bin/pip install -r services/api/requirements.txt -r services/vision/requirements.txt torch
```

**4. Download the recognition model once** (the start script runs it offline afterwards)

```bash
.venv/bin/python -c "from transformers import AutoModel, AutoProcessor; m='google/siglip2-base-patch16-224'; AutoModel.from_pretrained(m); AutoProcessor.from_pretrained(m)"
```

**5. Settings**

```bash
cp .env.example .env
```

For voice, create `apps/web/.env.local` containing one line, `ELEVENLABS_API_KEY=your-key` (this file is never
committed, and the key never reaches the browser). If you pulled `qwen3:4b`, start HomePilot with
`OLLAMA_MODEL=qwen3:4b` in front of the command (see below).

**6. Add a product gallery:** see [Teach it your products](#teach-it-your-products). The start script needs one at
`models/galleries/demo`.

## Start HomePilot

```bash
scripts/run-demo.sh --prod
```

The script checks everything above, starts Ollama, the vision service, the API and the web app, and prints when it's
ready. Open **http://localhost:3000** in Chrome or Safari. Press **Ctrl+C** in that terminal to stop everything.

Useful variations:

```bash
OLLAMA_MODEL=qwen3:4b scripts/run-demo.sh --prod          # smaller language model
scripts/run-demo.sh                                         # development mode (live reload)
```

Want to see the interface without any of the backend? Run only the web app (`cd apps/web && npm ci && npm run dev`)
and open **http://localhost:3000/?demo=1** for sample answers.

## Using HomePilot

1. **Wake it:** click **🎙 Listen** (allow the microphone), then say **"Hey HomePilot"**. The eyes become alert and the
   screen border glows. You can also simply **tap the eyes**.
2. **Ask:** say or type your request. To use a product photo, hold it up while the camera preview is on and press
   **📸 Send photo**, or use **🖼 Choose photo**.
3. **Confirm:** for items recognized from a photo, answer **yes** or **no**. By voice, say **"Hey HomePilot, yes"**.
4. Press **Back to HomePilot** to return to the eyes.

Tips: hold products front-on, close to the camera, in good light. Keep products that aren't in the gallery off to the
side during a demo.

## Teach it your products

HomePilot recognizes products by comparing your photo with reference photos in a gallery.

1. Make one folder per product, each with **3–5 photos taken with the camera you'll use** (front, slight angles):

   ```
   my_products/
     mms_peanut/      product.json  1.jpg 2.jpg 3.jpg
     celsius/         product.json  1.jpg 2.jpg 3.jpg
   ```

   `product.json` is optional and sets the display name, for example
   `{"name": "Peanut Chocolate Candies", "brand": "M&M's"}`. Without it, the folder name is used. Every subfolder becomes
   a product, so keep test photos somewhere else.

2. Build the gallery:

   ```bash
   .venv/bin/python services/vision/register_gallery.py --photos my_products --output models/galleries/demo
   ```

   It prints how often each photo matches its own product and suggests an "unknown" threshold, which the start script
   uses automatically. Re-run it whenever you add products. Galleries and photos are never committed to git.

**Optional fine-tuned model:** if you have the team's fine-tuned recognition model, build the gallery with
`--model "$PWD/models/siglip2-ft-2ep/best"` and start with
`VISION_MODEL="$PWD/models/siglip2-ft-2ep/best" VISION_UNKNOWN_THRESHOLD=0.80 scripts/run-demo.sh --prod`.
Use absolute paths: the model path must match the one stored in the gallery.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Microphone or camera is blocked | Use **http://localhost:3000**. Browsers only allow them on `localhost` or `https://`, not on a plain `http://` network address. To share with another computer, use HTTPS (for example `tailscale serve --bg 3000`). |
| "Voice will not work" warning at start | Add `ELEVENLABS_API_KEY` to `apps/web/.env.local` and restart. Typing and photos still work. |
| "Model qwen3:8b is missing" | Run `ollama pull qwen3:8b`, or start with `OLLAMA_MODEL=qwen3:4b`. |
| "No vision gallery" | Build one (see [Teach it your products](#teach-it-your-products)). |
| Vision service doesn't start on a new machine | Run setup step 4 once to download the recognition model. |
| "Port 8000/8001 is already in use" | Another copy is running; stop it (or press Ctrl+C in its terminal) and try again. |
| "The server isn't reachable" in the app | The API isn't running; start with `scripts/run-demo.sh`. Logs are printed at start-up. |
| Slow first answer | The language model is loading; later answers take a few seconds. On 8 GB Macs use `qwen3:4b`. |

## Privacy and security

- Your grocery list (`data/homepilot.sqlite3`), photos, galleries and models stay on your computer and are git-ignored.
- Voice audio is streamed to ElevenLabs only while listening is turned on; nothing reaches HomePilot before
  "Hey HomePilot". Typed and photo requests never leave your machine.
- There is **no login**. The start script keeps every part on `localhost`; if you expose it on a network, anyone who
  can reach it can change the list and use your ElevenLabs credit.
- Keep secrets in `.env` and `apps/web/.env.local` only; never commit them.

## For developers

- Read [AGENTS.md](AGENTS.md) first (coding agents too; Claude Code also reads [CLAUDE.md](CLAUDE.md)), then
  [MVP scope](docs/MVP_SCOPE.md), [architecture](docs/ARCHITECTURE.md), [API contracts](docs/API_CONTRACTS.md),
  [voice and capture](docs/VOICE_CAPTURE.md), [team ownership](docs/TEAM.md) and [decisions](docs/DECISIONS.md).
- API source of truth: [contracts/openapi.yaml](contracts/openapi.yaml). Recognition design:
  [RECOGNITION_DESIGN.md](docs/RECOGNITION_DESIGN.md). Training: [VISION_TRAINING.md](docs/VISION_TRAINING.md).
- Language model: `LLM_PROVIDER=ollama` (default) or `gemini` in `.env`.
- Tests:

  ```bash
  cd services/api && ../../.venv/bin/python -m pytest -q
  ../../.venv/bin/python scripts/orchestrator_validation.py
  ../../.venv/bin/python scripts/vision_service_validation.py
  cd ../.. && .venv/bin/python -m unittest discover -s services/vision/tests
  ```

- Work on short-lived branches; `main` is protected and only the repository owner can update it.
- Not built yet: inventory history ("when did we last get rice?"), the iPhone one-tap photo mode, Supabase hosting,
  cloud deployment, and the post-MVP Raspberry Pi robot (see [MVP_SCOPE.md](docs/MVP_SCOPE.md)).
