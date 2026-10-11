// Text-to-speech for HomePilot's spoken answers. The ElevenLabs key stays on the server; the browser
// only receives MP3 audio. Voice and model can be changed with ELEVENLABS_VOICE_ID / ELEVENLABS_TTS_MODEL.

const DEFAULT_VOICE = "cgSgspJ2msm6clMCkdW9"; // "Jessica": warm, conversational premade voice
const DEFAULT_MODEL = "eleven_flash_v2_5"; // lowest-latency model (~0.4 s for a short reply)
const MAX_CHARACTERS = 600;

export async function POST(request: Request) {
  const apiKey = process.env.ELEVENLABS_API_KEY?.trim();
  if (!apiKey) return Response.json({ error: "ElevenLabs API key is missing" }, { status: 500 });

  const body = await request.json().catch(() => null);
  const text = typeof body?.text === "string" ? body.text.trim().slice(0, MAX_CHARACTERS) : "";
  if (!text) return Response.json({ error: "text is required" }, { status: 400 });

  const voice = process.env.ELEVENLABS_VOICE_ID?.trim() || DEFAULT_VOICE;
  const model = process.env.ELEVENLABS_TTS_MODEL?.trim() || DEFAULT_MODEL;
  try {
    const response = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(voice)}/stream?output_format=mp3_44100_64`,
      {
        method: "POST",
        headers: { "xi-api-key": apiKey, "Content-Type": "application/json", Accept: "audio/mpeg" },
        body: JSON.stringify({
          text,
          model_id: model,
          voice_settings: { stability: 0.45, similarity_boost: 0.8, style: 0.3, use_speaker_boost: true },
        }),
        cache: "no-store",
      },
    );
    if (!response.ok || !response.body) {
      return Response.json({ error: "Speech could not be generated", providerStatus: response.status }, { status: 502 });
    }
    return new Response(response.body, { headers: { "Content-Type": "audio/mpeg", "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "ElevenLabs connection failed" }, { status: 502 });
  }
}
