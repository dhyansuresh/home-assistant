"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const MAX_SIDE = 1280; // keep uploads small; the vision model sees 224 px anyway

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const requestRef = useRef(0);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => {
    requestRef.current += 1; // a permission prompt that resolves later must not restart the camera
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setActive(false);
  }, []);

  useEffect(() => stop, [stop]);

  const start = useCallback(async (): Promise<boolean> => {
    if (streamRef.current) return true;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("The camera needs a supported browser on localhost or HTTPS. You can still choose a photo.");
      return false;
    }
    const request = ++requestRef.current;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      if (request !== requestRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return false;
      }
      streamRef.current = stream;
      stream.getVideoTracks().forEach((track) => track.addEventListener("ended", stop, { once: true }));
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setActive(true);
      return true;
    } catch (cause) {
      if (request !== requestRef.current) return false;
      stop();
      const name = cause instanceof DOMException ? cause.name : "";
      setError(name === "NotAllowedError" ? "Camera permission is blocked. Allow it in your browser, or choose a photo."
        : name === "NotFoundError" ? "No camera found. Connect one, or choose a photo."
        : "The camera couldn't start. Is another app using it?");
      return false;
    }
  }, [stop]);

  // The newest frame from the live preview as a JPEG, or null if the camera isn't ready.
  const grabFrame = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || !streamRef.current || video.readyState < 2 || !video.videoWidth) return null;
    const scale = Math.min(1, MAX_SIDE / Math.max(video.videoWidth, video.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
  }, []);

  return { videoRef, active, error, start, stop, grabFrame };
}
