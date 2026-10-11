
import { NextResponse } from "next/server";

export async function POST() {
  const apiKey = process.env.ELEVENLABS_API_KEY?.trim();

  if (!apiKey) {
    return NextResponse.json(
      { error: "ElevenLabs API key is missing" },
      { status: 500 }
    );
  }

  try {
    const response = await fetch(
      "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
      {
        method: "POST",
        headers: {
          "xi-api-key": apiKey,
        },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = body?.detail;
      const message = typeof detail === "string" ? detail : detail?.message;
      const error = typeof message === "string"
        ? message.split(apiKey).join("[redacted]")
        : "Could not create speech token";
      return NextResponse.json(
        { error, providerStatus: response.status },
        { status: 502 }
      );
    }

    const data = await response.json();

    if (typeof data.token !== "string" || !data.token) {
      return NextResponse.json(
        { error: "ElevenLabs did not return a speech token" },
        { status: 502 }
      );
    }

    return NextResponse.json({ token: data.token });
  } catch {
    return NextResponse.json(
      { error: "ElevenLabs connection failed" },
      { status: 502 }
    );
  }
}
