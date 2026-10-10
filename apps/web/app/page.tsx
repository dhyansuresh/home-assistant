"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export default function Home() {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const requestRef = useRef(0);

  const stopCamera = useCallback(() => {
    requestRef.current += 1;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraActive(false);
    setStarting(false);
    setReady(false);
  }, []);

  useEffect(() => {
    return () => {
      requestRef.current += 1;
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    return () => {
      if (imageUrl?.startsWith("blob:")) URL.revokeObjectURL(imageUrl);
    };
  }, [imageUrl]);

  async function startCamera() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Webcam access needs a supported browser on localhost or HTTPS. You can also choose a photo below.");
      return;
    }
    const request = ++requestRef.current;
    setStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      // Permission may resolve after Stop was clicked or this page was closed.
      if (request !== requestRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      stream.getVideoTracks().forEach((track) => track.addEventListener("ended", stopCamera, { once: true }));
      const video = videoRef.current;
      if (!video) {
        stopCamera();
        return;
      }
      video.srcObject = stream;
      setCameraActive(true);
      await video.play();
      if (request === requestRef.current) setStarting(false);
    } catch (cause) {
      if (request !== requestRef.current) return;
      stopCamera();
      const name = cause instanceof DOMException ? cause.name : "";
      setError(name === "NotAllowedError"
        ? "Camera permission was blocked. Allow camera access in your browser and try again, or choose a photo below."
        : name === "NotFoundError"
          ? "No webcam was found. Connect a camera or choose a photo below."
          : "The webcam could not start. Check whether another app is using it, then try again or choose a photo below.");
    }
  }

  function capturePhoto() {
    const video = videoRef.current;
    if (!video || !streamRef.current || video.readyState < 2 || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      setError("Could not capture this frame. Please try again or choose a photo.");
      return;
    }
    context.drawImage(video, 0, 0);
    setImageUrl(canvas.toDataURL("image/jpeg", 0.9));
    setFileName("Webcam photo");
    setError(null);
  }

  function preview(file: File | undefined) {
    if (!file) return;
    stopCamera();
    if (!file.type.startsWith("image/")) {
      setError("Please choose an image.");
      return;
    }
    setError(null);
    setImageUrl(URL.createObjectURL(file));
    setFileName(file.name);
  }

  return (
    <main className="shell">
      <div className="eyebrow">HomePilot · project starter</div>
      <h1>Know what is in your kitchen.</h1>
      <p className="intro">Take a grocery photo, review the suggestion, and keep your household list current.</p>

      <section className="card" aria-labelledby="camera-title">
        <h2 id="camera-title">Capture a product</h2>
        <p>Start your webcam, hold up a grocery item, and capture a photo. Photos stay on this device; recognition and saving are not connected yet.</p>
        <div className="camera-actions">
          <button className="capture" onClick={startCamera} disabled={starting || cameraActive}>
            {starting ? "Starting webcam…" : "Start webcam"}
          </button>
          <button className="capture" onClick={capturePhoto} disabled={!cameraActive || !ready}>
            Capture photo
          </button>
          <button className="capture secondary" onClick={stopCamera} disabled={!cameraActive && !starting}>
            Stop webcam
          </button>
        </div>
        <video
          className="preview"
          ref={videoRef}
          hidden={!cameraActive}
          autoPlay
          muted
          playsInline
          aria-label="Live webcam preview"
          onLoadedData={() => setReady(Boolean(streamRef.current))}
        />
        {error && <p role="alert">{error}</p>}
        <label className="capture secondary">
          Or choose an image
          <input
            type="file"
            accept="image/*"
            onChange={(event) => preview(event.target.files?.[0])}
          />
        </label>
        {fileName && <p className="filename" role="status">{fileName}</p>}
        {imageUrl && <img className="preview" src={imageUrl} alt="Selected grocery item preview" />}
      </section>

      <section className="next" aria-label="Planned MVP views">
        <h2>Coming in the MVP</h2>
        <ul>
          <li>Review and correct a product prediction</li>
          <li>Save confirmed items to inventory</li>
          <li>Ask the assistant to update a grocery list</li>
        </ul>
      </section>
    </main>
  );
}
