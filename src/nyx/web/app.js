"use strict";

const $ = (id) => document.getElementById(id);
const MAX_BYTES = 256 * 1024 * 1024;
let recorder = null;
let stream = null;
let pending = null;
let previewUrl = null;
let timer = null;
let startedAt = null;
let busy = false;
let requestingCamera = false;

function message(text, error = false) {
  $(error ? "error" : "task").textContent = text;
  $(error ? "error" : "task").hidden = !text;
}

function controls() {
  const recording = recorder && recorder.state !== "inactive";
  $("start").hidden = Boolean(recording || pending);
  $("start").disabled = busy || requestingCamera;
  $("stop").hidden = !recording;
  $("save").hidden = !pending;
  $("save").disabled = busy;
  $("discard").hidden = !pending;
  $("discard").disabled = busy;
  $("file").disabled = busy || Boolean(recording || pending) || requestingCamera;
  $("search").disabled = busy || Boolean(recording) || requestingCamera;
  $("recording-badge").hidden = !recording;
  $("camera-state").classList.toggle("active", Boolean(recording));
  $("camera-state").lastChild.textContent = recording ? "Recording video" : "Camera off";
}

function releaseCamera() {
  if (stream) stream.getTracks().forEach((track) => track.stop());
  stream = null;
  clearInterval(timer);
  timer = null;
}

function clearPreview() {
  $("viewer").pause();
  $("viewer").srcObject = null;
  $("viewer").removeAttribute("src");
  $("viewer").load();
  $("viewer").hidden = true;
  $("empty-preview").hidden = false;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null;
}

function timestamp(seconds) {
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
}

async function api(path, options) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Check the input and try again.");
  return body;
}

async function task(path, options) {
  busy = true;
  message("");
  message("", true);
  controls();
  try {
    const job = await api(path, options);
    while (true) {
      const state = await api(`/api/jobs/${job.id}`);
      if (state.status === "succeeded") return state.result;
      if (state.status === "failed") throw new Error(state.error);
      message(state.kind === "index" ? "Indexing your clip locally. The first clip may take a little longer." : "Searching your clips locally…");
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  } finally {
    busy = false;
    controls();
  }
}

function play(source, offset, caption) {
  if (stream || pending || requestingCamera) {
    message("Stop recording, then index or discard your clip before replaying another.");
    return;
  }
  const viewer = $("viewer");
  viewer.srcObject = null;
  viewer.muted = false;
  viewer.controls = true;
  viewer.src = `${source}#t=${offset}`;
  viewer.hidden = false;
  $("empty-preview").hidden = true;
  $("preview-caption").textContent = caption;
  viewer.play().catch(() => {});
}

async function refreshLibrary() {
  const videos = await api("/api/videos");
  const scope = $("scope").value;
  $("scope").replaceChildren(new Option("All clips", ""));
  $("clips").replaceChildren();
  const ready = videos.filter((video) => video.status === "ready");
  $("clip-count").textContent = `${ready.length} ${ready.length === 1 ? "clip" : "clips"}`;
  for (const video of videos) {
    const button = document.createElement("button");
    button.className = `clip ${video.status}`;
    const title = document.createElement("strong");
    title.textContent = video.name;
    const detail = document.createElement("small");
    detail.textContent = video.status === "ready"
      ? `${video.frame_count} sampled moments · ${video.recorded_at ? new Date(video.recorded_at).toLocaleString() : "Capture time unknown"}`
      : video.status === "failed" ? "Indexing failed. Try another clip." : "Indexing unfinished; excluded from search.";
    button.append(title, detail);
    if (video.status === "ready") {
      $("scope").add(new Option(video.name, video.id));
      button.onclick = () => {
        $("scope").value = video.id;
        play(`/api/videos/${video.id}/media`, 0, `${video.name} · Source clip`);
      };
    } else {
      button.disabled = true;
    }
    $("clips").append(button);
  }
  if (!videos.length) {
    const empty = document.createElement("p");
    empty.className = "empty-library";
    empty.textContent = "Your indexed clips will appear here.";
    $("clips").append(empty);
  }
  if (ready.some((video) => video.id === scope)) $("scope").value = scope;
}

$("start").onclick = async () => {
  message("", true);
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    message("This browser cannot record video here. Import a video instead.", true);
    return;
  }
  requestingCamera = true;
  controls();
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    clearPreview();
    const chunks = [];
    let size = 0;
    const mimeType = ["video/webm;codecs=vp8", "video/webm", "video/mp4"].find((type) => MediaRecorder.isTypeSupported(type));
    recorder = new MediaRecorder(stream, { ...(mimeType ? { mimeType } : {}), videoBitsPerSecond: 2500000 });
    recorder.ondataavailable = (event) => {
      if (event.data.size) { chunks.push(event.data); size += event.data.size; }
      if (size > MAX_BYTES && recorder.state !== "inactive") recorder.stop();
    };
    recorder.onerror = () => {
      message("Recording failed. Stop and try again, or import a video.", true);
      if (recorder.state !== "inactive") recorder.stop();
      releaseCamera();
    };
    recorder.onstop = () => {
      const type = recorder.mimeType;
      releaseCamera();
      $("viewer").srcObject = null;
      const blob = new Blob(chunks, { type });
      if (!blob.size || blob.size > MAX_BYTES) {
        clearPreview();
        message("The recording is empty or too large. Try a shorter clip.", true);
        controls();
        return;
      }
      pending = { blob, name: `nyx-${startedAt.replaceAll(":", "-")}.${type.includes("mp4") ? "mp4" : "webm"}`, recordedAt: startedAt };
      previewUrl = URL.createObjectURL(blob);
      $("viewer").src = previewUrl;
      $("viewer").controls = true;
      $("preview-caption").textContent = "Preview your clip, then index it or discard it. Camera is off.";
      controls();
    };
    stream.getVideoTracks()[0].onended = () => {
      if (recorder.state !== "inactive") {
        message("The camera stopped unexpectedly. The saved clip may be incomplete.", true);
        recorder.stop();
      }
    };
    stream.getVideoTracks()[0].onmute = () => {
      if (recorder.state !== "inactive") {
        message("Camera frames were interrupted. Recording stopped; the clip may be incomplete.", true);
        recorder.stop();
      }
    };
    const viewer = $("viewer");
    viewer.srcObject = stream;
    viewer.muted = true;
    viewer.controls = false;
    viewer.hidden = false;
    $("empty-preview").hidden = true;
    await viewer.play();
    startedAt = new Date().toISOString();
    recorder.start(1000);
    $("elapsed").textContent = "00:00";
    $("preview-caption").textContent = "Recording video only. Stop when you have a useful moment.";
    const start = performance.now();
    timer = setInterval(() => {
      const elapsed = (performance.now() - start) / 1000;
      $("elapsed").textContent = timestamp(elapsed);
      if (elapsed >= 120 && recorder.state !== "inactive") recorder.stop();
    }, 250);
  } catch (error) {
    releaseCamera();
    clearPreview();
    message(error.name === "NotAllowedError" ? "Camera access was denied. Allow it in your browser, or import a video." : `Could not start the camera: ${error.message}`, true);
  } finally {
    requestingCamera = false;
    controls();
  }
};

$("stop").onclick = () => { if (recorder && recorder.state !== "inactive") recorder.stop(); };
$("discard").onclick = () => {
  pending = null;
  clearPreview();
  $("preview-caption").textContent = "Clip discarded. Start again whenever you’re ready.";
  controls();
};

async function indexClip(blob, name, recordedAt) {
  if (blob.size > MAX_BYTES) throw new Error("Choose a clip smaller than 256 MiB.");
  message("Sending the clip to Nyx on this laptop…");
  const params = new URLSearchParams({ name });
  if (recordedAt) params.set("recorded_at", recordedAt);
  const result = await task(`/api/import?${params}`, { method: "POST", body: blob });
  pending = null;
  clearPreview();
  controls();
  await refreshLibrary();
  $("scope").value = result.video_id;
  play(`/api/videos/${result.video_id}/media`, 0, `${name} · Indexed source clip`);
  message(`Clip indexed. ${result.frame_count} sampled moments are ready to search.`);
}

$("save").onclick = async () => {
  try { await indexClip(pending.blob, pending.name, pending.recordedAt); }
  catch (error) { message(""); message(error.message, true); await refreshLibrary(); }
};
$("file").onchange = async () => {
  const file = $("file").files[0];
  if (!file) return;
  try { await indexClip(file, file.name, null); }
  catch (error) { message(""); message(error.message, true); await refreshLibrary(); }
  finally { $("file").value = ""; }
};

$("search-form").onsubmit = async (event) => {
  event.preventDefault();
  if (busy || requestingCamera || (recorder && recorder.state !== "inactive")) return;
  const query = $("query").value.trim();
  if (!query) return;
  try {
    const output = await task("/api/search", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query, video_id: $("scope").value || null }) });
    $("results").replaceChildren();
    $("search-results").hidden = false;
    $("result-count").textContent = `${output.results.length} candidates`;
    for (const result of output.results) {
      const button = document.createElement("button");
      button.className = "candidate";
      const image = document.createElement("img");
      image.src = result.thumbnail_url;
      image.alt = `Candidate at ${timestamp(result.offset_seconds)}`;
      const text = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = `${timestamp(result.offset_seconds)} · Play source`;
      const name = document.createElement("span");
      name.textContent = result.name;
      const score = document.createElement("small");
      score.textContent = `Similarity ${result.similarity.toFixed(3)} · Unverified`;
      text.append(title, name, score);
      button.append(image, text);
      button.onclick = () => play(result.media_url, result.offset_seconds, `${result.name} · Candidate at ${timestamp(result.offset_seconds)}`);
      $("results").append(button);
    }
    message(output.results.length ? "Select a candidate to replay its source moment." : "No searchable frames in this clip. Choose another clip or import one.");
  } catch (error) { message(""); message(error.message, true); }
};

window.addEventListener("pagehide", () => {
  if (recorder && recorder.state !== "inactive") recorder.stop();
  releaseCamera();
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden && recorder && recorder.state !== "inactive") {
    message("Recording stopped when this tab was hidden. Review the clip before indexing it.", true);
    recorder.stop();
    releaseCamera();
  }
});
controls();
refreshLibrary().catch((error) => message(`Could not load the library: ${error.message}`, true));
