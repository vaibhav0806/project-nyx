"use strict";

const $ = (id) => document.getElementById(id);
const SEGMENT_BYTES = 32 * 1024 * 1024;
let stream = null;
let current = null;
let captureSession = null;
let remoteSession = null;
let enabled = false;
let paused = false;
let requestingCamera = false;
let generation = 0;
let sequence = 0;
let segmentSeconds = 10;
let rotation = null;
let clock = null;
let heartbeat = null;
let startedAt = null;
let busy = false;
let uploads = [];
let uploading = false;
let uploadFailed = false;
let downloadUrl = null;
let latestReadyCount = null;
let finalizing = 0;
let clipsShown = 50;

function message(text, error = false) {
  $(error ? "error" : "task").textContent = text;
  $(error ? "error" : "task").hidden = !text;
}

function controls() {
  $("start").hidden = enabled || paused || Boolean(remoteSession);
  $("start").disabled = busy || requestingCamera || uploads.length > 0 || finalizing > 0;
  $("stop").hidden = !(enabled || paused || requestingCamera || remoteSession);
  $("pause").hidden = !enabled;
  $("resume").hidden = !paused;
  $("resume").disabled = requestingCamera || uploadFailed || finalizing > 0;
  $("file").disabled = busy || enabled || paused || requestingCamera;
  $("search").disabled = busy;
  $("ask-history").disabled = busy;
  $("inspect-now").disabled = busy || !enabled || !stream;
  $("show-older-clips").disabled = busy;
  document.querySelectorAll(".delete-clip").forEach((button) => { button.disabled = busy || enabled || paused || requestingCamera || Boolean(remoteSession) || uploads.length > 0 || finalizing > 0; });
  $("recording-badge").hidden = !enabled;
  $("camera-state").classList.toggle("active", enabled);
  $("camera-state").lastChild.textContent = enabled ? "Recording video" : paused ? "Recording paused" : "Camera off";
}

function timestamp(seconds) {
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
}

function localTime(value) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(typeof body.detail === "string" ? body.detail : "Check the input and try again.");
    error.status = response.status;
    throw error;
  }
  return body;
}

function json(body) {
  return { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
}

async function task(path, options, onJob = () => {}) {
  busy = true;
  controls();
  message("", true);
  try {
    const job = await api(path, options);
    onJob(job.id);
    while (true) {
      const state = await api(`/api/jobs/${job.id}`);
      if (state.status === "succeeded") return state.result;
      if (state.status === "failed") throw new Error(state.error);
      message(state.kind === "index" ? "Indexing your imported clip locally…" : state.kind === "answer" ? `Checking visual evidence locally${state.progress?.checked ? ` · ${state.progress.checked} frames checked` : " · first use loads the visual model"}…` : "Searching saved moments…");
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  } finally {
    busy = false;
    controls();
  }
}

function play(source, offset, caption) {
  const replay = $("replay");
  replay.src = `${source}#t=${offset}`;
  $("replay-panel").hidden = false;
  $("replay-caption").textContent = caption;
  replay.play().catch(() => {});
}

async function refreshLibrary() {
  const videos = await api("/api/videos");
  const capture = await api("/api/capture");
  const registered = new Set(videos.map((video) => video.id));
  for (const segment of capture.segments) {
    if (!registered.has(segment.id) && segment.size > 0 && ["failed", "deleting"].includes(segment.state)) {
      videos.push({ id: segment.id, name: `Recording ${segment.recorded_at} · part ${segment.sequence + 1}`, status: segment.state, frame_count: 0, recorded_at: segment.timing_uncertain ? null : segment.recorded_at, media_url: `/api/capture/segments/${segment.id}/media` });
    }
  }
  const scope = $("scope").value;
  $("scope").replaceChildren(new Option("All clips", ""));
  $("clips").replaceChildren();
  const ready = videos.filter((video) => video.status === "ready");
  $("clip-count").textContent = `${ready.length} ${ready.length === 1 ? "clip" : "clips"}`;
  for (const video of videos.slice(0, clipsShown)) {
    const row = document.createElement("div");
    row.className = "clip-row";
    const button = document.createElement("button");
    button.className = `clip ${video.status}`;
    const title = document.createElement("strong");
    title.textContent = video.name;
    const detail = document.createElement("small");
    detail.textContent = video.status === "ready"
      ? `${video.frame_count} sampled moments · ${video.recorded_at ? new Date(video.recorded_at).toLocaleString() : "Capture time unknown"}`
      : video.status === "deleting" ? "Deletion incomplete; retry to finish cleanup." : video.status === "failed" ? "Indexing failed; excluded from search." : "Indexing; excluded until complete.";
    button.append(title, detail);
    if (video.status === "ready" || (video.media_url && video.status === "failed")) {
      button.onclick = () => play(video.media_url || `/api/videos/${video.id}/media`, 0, `${video.name} · Source clip`);
    } else {
      button.disabled = true;
    }
    row.append(button);
    if (["ready", "failed", "deleting"].includes(video.status)) {
      const remove = document.createElement("button");
      remove.className = "delete-clip";
      remove.textContent = video.status === "deleting" ? "Retry deletion" : "Delete clip";
      remove.setAttribute("aria-label", remove.textContent);
      remove.onclick = () => deleteClip(video);
      row.append(remove);
    }
    $("clips").append(row);
  }
  for (const video of ready) $("scope").add(new Option(video.name, video.id));
  $("show-older-clips").hidden = videos.length <= clipsShown;
  if (!videos.length) {
    const empty = document.createElement("p");
    empty.className = "empty-library";
    empty.textContent = "Saved segments appear here automatically while recording.";
    $("clips").append(empty);
  }
  if (ready.some((video) => video.id === scope)) $("scope").value = scope;
  controls();
}

$("show-older-clips").onclick = async () => {
  clipsShown += 50;
  try { await refreshLibrary(); }
  catch (error) { message(error.message, true); }
};

async function deleteClip(video) {
  if (!window.confirm(`Permanently delete “${video.name}”? Its saved video, thumbnails and search vectors will be removed. This cannot be undone.`)) return;
  busy = true;
  controls();
  message("", true);
  message("Deleting clip and its search data…");
  try {
    await api(`/api/videos/${video.id}`, { method: "DELETE" });
    window.dispatchEvent(new Event("nyx-source-deleted"));
    $("search-results").hidden = true;
    $("answer-panel").hidden = true;
    $("answer-evidence").replaceChildren();
    $("answer-checks").replaceChildren();
    $("snapshot-evidence").removeAttribute("src");
    $("results").replaceChildren();
    $("replay").pause();
    $("replay").removeAttribute("src");
    $("replay").load();
    $("replay-panel").hidden = true;
    $("scope").value = "";
    await refreshLibrary();
    await refreshCoverage();
    message("Clip deleted, including its thumbnails and search vectors.");
  } catch (error) {
    message("");
    message(error.message, true);
    await refreshLibrary().catch(() => {});
  } finally {
    busy = false;
    controls();
  }
}

async function refreshCoverage() {
  const status = await api("/api/capture");
  segmentSeconds = status.segment_seconds;
  remoteSession = status.session && ["recording", "paused"].includes(status.session.state) && status.session.id !== captureSession?.id ? status.session : null;
  $("saved-through").textContent = status.recorded_through ? `Saved through ${localTime(status.recorded_through)}` : "No continuous segments saved yet.";
  $("searchable-through").textContent = status.searchable_through ? `Searchable through ${localTime(status.searchable_through)} · sampled every ${status.sample_seconds}s` : "The first completed segment will become searchable automatically.";
  $("storage").textContent = `Saved video: ${(status.video_bytes / 1024**2).toFixed(1)} / ${(status.video_budget_bytes / 1024**2).toFixed(0)} MiB. Existing clips are kept. Thumbnails and model cache are additional.`;
  const pending = ["uploading", "staged", "queued", "indexing"].reduce((total, state) => total + (status.counts[state] || 0), 0);
  const failed = status.counts.failed || 0;
  $("backlog").textContent = `${pending} segments waiting or indexing${failed ? `; ${failed} failed segments are excluded from search` : ""}.${status.timing_uncertain_count ? ` ${status.timing_uncertain_count} saved segments have uncertain clock times; their clip offsets remain searchable.` : ""}`;
  $("capture-events").replaceChildren();
  for (const event of status.events) {
    const line = document.createElement("p");
    line.textContent = `${localTime(event.at)} · ${event.reason}`;
    $("capture-events").append(line);
  }
  for (const segment of status.segments.filter((segment) => segment.state === "failed" && segment.size > 0)) {
    const button = document.createElement("button");
    button.textContent = "Play saved segment · indexing failed";
    button.onclick = () => play(`/api/capture/segments/${segment.id}/media`, 0, "Saved source · not searchable");
    $("capture-events").append(button);
  }
  if (!status.events.length && !failed) $("capture-events").textContent = "No recorded interruptions.";
  if (remoteSession) $("preview-caption").textContent = "A recording session is open in another tab, or its connection was lost. Stop it before starting here.";
  const readyCount = status.counts.ready || 0;
  if (readyCount !== latestReadyCount) {
    latestReadyCount = readyCount;
    await refreshLibrary();
  }
  controls();
  return status;
}

function releaseCamera() {
  if (stream) stream.getTracks().forEach((track) => track.stop());
  stream = null;
  clearTimeout(rotation);
  clearInterval(clock);
  clearInterval(heartbeat);
  rotation = clock = heartbeat = null;
  $("viewer").srcObject = null;
  $("viewer").hidden = true;
  $("empty-preview").hidden = false;
}

function finishSegment(segment, uncertain = false) {
  if (segment && (uncertain || Date.now() - Date.parse(segment.recordedAt) > (segmentSeconds + 5) * 1000)) segment.timingUncertain = true;
  if (segment && segment.recorder.state !== "inactive") {
    segment.endedAt = new Date().toISOString();
    segment.finalizing = true;
    finalizing++;
    segment.recorder.stop();
  }
}

async function stopCapture(reason = "Stopped by user", state = "stopped") {
  const stoppedSession = captureSession;
  const id = stoppedSession?.id || remoteSession?.id;
  generation++;
  enabled = false;
  paused = state === "paused";
  if (!paused) captureSession = null;
  requestingCamera = false;
  finishSegment(current, state === "interrupted");
  current = null;
  releaseCamera();
  controls();
  $("preview-caption").textContent = paused ? "Camera off. Resume when you’re ready; the pause stays in recording history." : "Camera off. Completed segments keep indexing in the background.";
  if (id) {
    try { await api(`/api/capture/${id}/state`, json({ state, at: new Date().toISOString(), reason })); }
    catch (error) { message(`Camera stopped. Could not confirm session state: ${error.message}`, true); }
  }
  remoteSession = null;
  if (!paused) window.dispatchEvent(new Event("nyx-camera-stopped"));
  refreshCoverage().catch(() => {});
}

function showUnsaved() {
  $("unsaved").hidden = !uploads.length;
  $("retry-upload").disabled = uploading;
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  downloadUrl = null;
  if (uploads.length) {
    downloadUrl = URL.createObjectURL(uploads[0].blob);
    $("download-segment").href = downloadUrl;
    $("download-segment").download = `nyx-unsaved-${uploads[0].sequence}.${uploads[0].format}`;
  }
  controls();
}

async function pumpUploads() {
  if (uploading || uploadFailed) return;
  uploading = true;
  try {
    while (uploads.length) {
      const item = uploads[0];
      const params = new URLSearchParams({ recorded_at: item.recordedAt, ended_at: item.endedAt, format: item.format, timing_uncertain: Boolean(item.timingUncertain) });
      let saved = false;
      let lastError;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          const result = await api(`/api/capture/${item.sessionId}/segments/${item.sequence}?${params}`, { method: "POST", body: item.blob, signal: AbortSignal.timeout(15000) });
          if (result.state === "failed") throw new Error("A saved segment could not be indexed. Check recording history.");
          saved = true;
          break;
        } catch (error) {
          lastError = error;
          if (error.status && error.status !== 409 && error.status < 500) break;
          await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
        }
      }
      if (!saved) throw lastError;
      uploads.shift();
      await refreshCoverage();
    }
  } catch (error) {
    uploadFailed = true;
    message(`Recording stopped: ${error.message} Saved clips are kept.`, true);
    await stopCapture(`Saving failed: ${error.message}`.slice(0, 300), "interrupted");
  } finally {
    uploading = false;
    showUnsaved();
  }
}

function makeSegment() {
  const mimeType = ["video/webm;codecs=vp8", "video/webm", "video/mp4"].find((type) => MediaRecorder.isTypeSupported(type));
  const recorder = new MediaRecorder(stream, { ...(mimeType ? { mimeType } : {}), videoBitsPerSecond: 2500000 });
  const segment = { recorder, sessionId: captureSession.id, sequence: sequence++, recordedAt: new Date().toISOString(), endedAt: null, chunks: [], size: 0 };
  recorder.ondataavailable = (event) => {
    if (event.data.size) { segment.chunks.push(event.data); segment.size += event.data.size; }
    if (segment.size > SEGMENT_BYTES && enabled) {
      message("Recording stopped: the current segment grew too large. Saved clips are kept.", true);
      stopCapture("Segment size limit reached", "interrupted");
    }
  };
  recorder.onerror = () => {
    message("The recorder failed. Completed segments are kept; the current segment may be incomplete.", true);
    stopCapture("Recorder failed; current segment may be incomplete", "interrupted");
  };
  recorder.onstop = () => {
    if (segment.finalizing) finalizing--;
    const blob = new Blob(segment.chunks, { type: recorder.mimeType });
    if (!blob.size) {
      message("A recording segment was empty and was not saved.", true);
      controls();
      return;
    }
    uploads.push({ blob, timingUncertain: Boolean(segment.timingUncertain), sessionId: segment.sessionId, sequence: segment.sequence, recordedAt: segment.recordedAt, endedAt: segment.endedAt || new Date().toISOString(), format: recorder.mimeType.includes("mp4") ? "mp4" : "webm" });
    if (uploads.length > 3 && enabled) {
      message("Saving cannot keep up. Recording stopped; pending segments are being saved.", true);
      stopCapture("Upload backlog; recording stopped", "interrupted");
    }
    controls();
    pumpUploads();
  };
  recorder.start(1000);
  return segment;
}

function rotateSegment() {
  if (!enabled || !stream) return;
  try {
    if (current && Date.now() - Date.parse(current.recordedAt) > (segmentSeconds + 5) * 1000) {
      message("Recording stopped after a browser or sleep interruption. Recent coverage may have gaps.", true);
      stopCapture("Browser or sleep interruption; recent coverage is uncertain", "interrupted");
      return;
    }
    const previous = current;
    current = makeSegment();
    finishSegment(previous);
    rotation = setTimeout(rotateSegment, segmentSeconds * 1000);
  } catch (error) {
    message(`Recording stopped: ${error.message}`, true);
    stopCapture("Could not rotate recording segment", "interrupted");
  }
}

async function startCapture(resume = false) {
  const ownGeneration = ++generation;
  requestingCamera = true;
  message("", true);
  controls();
  try {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("This browser cannot record video; import a clip instead.");
    if (!uploads.length) uploadFailed = false;
    if (resume) {
      await api(`/api/capture/${captureSession.id}/state`, json({ state: "recording", at: new Date().toISOString(), reason: "Resumed by user" }));
    } else {
      const created = await api("/api/capture/start", json({ at: new Date().toISOString() }));
      if (generation !== ownGeneration) {
        await api(`/api/capture/${created.id}/state`, json({ state: "stopped", at: new Date().toISOString(), reason: "Start cancelled by user" }));
        return;
      }
      captureSession = created;
      sequence = 0;
      startedAt = Date.now();
    }
    if (generation !== ownGeneration) return;
    const acquired = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    if (generation !== ownGeneration) { acquired.getTracks().forEach((track) => track.stop()); return; }
    stream = acquired;
    const viewer = $("viewer");
    viewer.srcObject = stream;
    viewer.muted = true;
    viewer.controls = false;
    viewer.hidden = false;
    $("empty-preview").hidden = true;
    await viewer.play();
    if (generation !== ownGeneration) return;
    enabled = true;
    paused = false;
    current = makeSegment();
    rotation = setTimeout(rotateSegment, segmentSeconds * 1000);
    $("scope").value = "";
    $("preview-caption").textContent = "Recording video. Completed segments save and index automatically; you can search while recording.";
    const interrupt = () => {
      if (enabled) {
        message("The camera was interrupted. Recording stopped; coverage after the last saved segment may be incomplete.", true);
        stopCapture("Camera interrupted; current segment may be incomplete", "interrupted");
      }
    };
    stream.getVideoTracks()[0].onended = interrupt;
    stream.getVideoTracks()[0].onmute = interrupt;
    let lastTick = Date.now();
    clock = setInterval(() => {
      const now = Date.now();
      $("elapsed").textContent = timestamp((now - startedAt) / 1000);
      if (now - lastTick > 30000) {
        message("Recording stopped after a browser or sleep interruption. Recent coverage may have gaps.", true);
        stopCapture("Browser or sleep interruption; recent coverage is uncertain", "interrupted");
      }
      lastTick = now;
    }, 1000);
    heartbeat = setInterval(async () => {
      if (!enabled || !captureSession) return;
      try {
        const state = await api(`/api/capture/${captureSession.id}/heartbeat`, { method: "POST", signal: AbortSignal.timeout(10000) });
        if (enabled && state.state !== "recording") await stopCapture("Recording stopped from another session", "interrupted");
      } catch (error) {
        if (enabled) {
          message("Connection to Nyx was lost. Recording stopped; the last segment may still need saving.", true);
          stopCapture("Connection lost; unsaved tail may be missing", "interrupted");
        }
      }
    }, 5000);
  } catch (error) {
    if (generation !== ownGeneration) return;
    message(error.name === "NotAllowedError" ? "Camera access was denied. Allow it in your browser, or import a video." : `Could not start recording: ${error.message}`, true);
    if (captureSession && generation === ownGeneration) await stopCapture("Could not start camera", "interrupted");
  } finally {
    if (generation === ownGeneration) requestingCamera = false;
    controls();
  }
}

$("start").onclick = () => startCapture();
$("resume").onclick = () => startCapture(true);
$("pause").onclick = () => stopCapture("Paused by user", "paused");
$("stop").onclick = () => stopCapture();
$("retry-upload").onclick = () => { uploadFailed = false; pumpUploads(); };

$("file").onchange = async () => {
  const file = $("file").files[0];
  if (!file) return;
  try {
    const result = await task(`/api/import?${new URLSearchParams({ name: file.name })}`, { method: "POST", body: file });
    await refreshLibrary();
    $("scope").value = result.video_id;
    play(`/api/videos/${result.video_id}/media`, 0, `${file.name} · Indexed source clip`);
    message(`Clip indexed. ${result.frame_count} sampled moments are ready to search.`);
  } catch (error) { message(""); message(error.message, true); }
  finally { $("file").value = ""; }
};

$("search-form").onsubmit = async (event) => {
  event.preventDefault();
  const query = $("query").value.trim();
  if (!query || busy) return;
  try {
    const output = await task("/api/search", json({ query, video_id: $("scope").value || null }));
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
      name.textContent = result.recorded_at ? new Date(new Date(result.recorded_at).getTime() + result.offset_seconds * 1000).toLocaleString() : `${result.name} · Clock time uncertain; use clip offset`;
      const score = document.createElement("small");
      score.textContent = `Similarity ${result.similarity.toFixed(3)} · Unverified`;
      text.append(title, name, score);
      button.append(image, text);
      button.onclick = () => play(result.media_url, result.offset_seconds, `${result.name} · Candidate at ${timestamp(result.offset_seconds)}`);
      $("results").append(button);
    }
    message(output.results.length ? "Select a candidate to replay it. Recording can keep running." : "No searchable frames yet for these filters. Recording and indexing can keep running.");
  } catch (error) { message(""); message(error.message, true); }
};

function answerEvidence(row, label) {
  const button = document.createElement("button");
  button.className = "candidate";
  const image = document.createElement("img");
  image.src = row.thumbnail_url;
  image.alt = `${label} at ${timestamp(row.offset_seconds)}`;
  const text = document.createElement("span");
  text.textContent = `${label} · ${timestamp(row.offset_seconds)} · ${row.observed_at ? new Date(row.observed_at).toLocaleString() : "Capture clock time unknown"}`;
  button.append(image, text);
  button.onclick = () => play(row.media_url, row.offset_seconds, `${row.name || "Source"} · ${label} at ${timestamp(row.offset_seconds)}`);
  return button;
}

function showAnswer(output) {
  $("answer-panel").hidden = false;
  const observed = output.captured_at || output.evidence?.observed_at;
  $("answer-text").textContent = observed ? output.answer.replace(observed, new Date(observed).toLocaleString()) : output.answer;
  $("answer-note").textContent = output.status === "confirmed"
    ? "You confirmed this item in a saved frame. This is historical evidence, not its current location."
    : output.kind === "snapshot"
    ? `Snapshot age when answered: ${Math.max(0, output.age_seconds).toFixed(1)}s. The view may have changed. This snapshot is not saved to permanent history.`
    : `Checked ${output.scope.checked_count} sampled moments. This may miss sightings in other footage or recording gaps.${output.scope.known_time_only ? " Unknown capture dates were excluded." : ""}`;
  $("answer-evidence").replaceChildren();
  $("answer-checks").replaceChildren();
  $("snapshot-evidence").hidden = !output.snapshot_url;
  if (output.snapshot_url) $("snapshot-evidence").src = output.snapshot_url;
  else $("snapshot-evidence").removeAttribute("src");
  if (output.evidence) $("answer-evidence").append(answerEvidence(output.evidence,
    output.status === "confirmed" ? "You confirmed this item" : "Possible match · check the item"));
  if (!output.evidence) {
    const ambiguous = (output.checked || []).find(row => row.judgment?.ambiguous);
    if (ambiguous) $("answer-evidence").append(answerEvidence(ambiguous, "Several possible items · needs clarification"));
  }
  if (output.status === "candidate" && output.evidence) {
    const confirm = document.createElement("button");
    confirm.textContent = "This is the item";
    const reject = document.createElement("button");
    reject.textContent = "Not this item";
    const requestId = crypto.randomUUID();
    const review = async (operation) => {
      confirm.disabled = reject.disabled = true;
      try {
        const result = await operation();
        showAnswer(result);
        if (typeof companion !== "undefined") await companion.refresh();
      } catch (error) {
        message(error.message, true);
        confirm.disabled = reject.disabled = false;
      }
    };
    confirm.onclick = () => review(() => api("/api/matches/confirm", json({
      frame_id: output.evidence.id, object_query: output.object_query, request_id: requestId,
    })));
    reject.onclick = () => review(() => task("/api/answer", json({
      object_query: output.object_query, mode: output.scope.mode,
      video_id: output.scope.video_id || null,
      seen_after: output.scope.seen_after, seen_before: output.scope.seen_before,
      excluded_frame_ids: [...(output.scope.excluded_frame_ids || []), output.evidence.id],
    })));
    $("answer-evidence").append(confirm, reject);
  }
  for (const row of output.checked || []) {
    const line = document.createElement("p");
    line.textContent = `${row.observed_at ? new Date(row.observed_at).toLocaleString() : `Clock unknown, offset ${timestamp(row.offset_seconds)}`} · ${row.judgment.visibility}: ${row.judgment.description}`;
    $("answer-checks").append(line);
  }
  for (const row of output.evidence?.context || []) $("answer-checks").append(answerEvidence(row, "Nearby sample · unverified context"));
  const scope = document.createElement("p");
  scope.textContent = output.scope.note;
  $("answer-checks").append(scope);
  if (output.verifier) {
    const model = document.createElement("p");
    model.className = "help";
    model.textContent = `Local model: ${output.verifier.model}`;
    $("answer-checks").append(model);
  }
}

$("answer-form").onsubmit = async (event) => {
  event.preventDefault();
  const objectQuery = $("object-query").value.trim();
  if (!objectQuery || busy) return;
  $("answer-panel").hidden = true;
  try {
    const after = $("seen-after").value ? new Date($("seen-after").value).toISOString() : null;
    const before = $("seen-before").value ? new Date($("seen-before").value).toISOString() : null;
    if (after && before && after > before) throw new Error("From must be earlier than Until.");
    const output = await task("/api/answer", json({ object_query: objectQuery, mode: $("history-mode").value, video_id: $("scope").value || null, seen_after: after, seen_before: before }));
    showAnswer(output);
    message("Visual check complete. Review the source and the checked time range.");
  } catch (error) { message(""); message(error.message, true); }
};

async function inspectView(objectQuery, onJob) {
  const viewer = $("viewer");
  if (!enabled || !stream || !viewer.videoWidth) throw new Error("Start the camera before checking the current view.");
  const capturedAt = new Date().toISOString();
  const canvas = document.createElement("canvas");
  const scale = Math.min(1, 1280 / viewer.videoWidth, 720 / viewer.videoHeight);
  canvas.width = Math.floor(viewer.videoWidth * scale);
  canvas.height = Math.floor(viewer.videoHeight * scale);
  canvas.getContext("2d").drawImage(viewer, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
  if (!blob) throw new Error("Could not capture a snapshot; try again.");
  return task(`/api/inspect?${new URLSearchParams({ object_query: objectQuery, captured_at: capturedAt })}`, { method: "POST", body: blob }, onJob);
}

$("inspect-now").onclick = async () => {
  const objectQuery = $("object-query").value.trim();
  if (busy || !objectQuery || !$("answer-form").reportValidity()) return;
  $("answer-panel").hidden = true;
  try {
    showAnswer(await inspectView(objectQuery));
    message("Snapshot checked locally. Its capture time is shown with the answer.");
  } catch (error) { message(""); message(error.message, true); }
};

window.addEventListener("pagehide", () => {
  const id = captureSession?.id;
  generation++;
  enabled = false;
  finishSegment(current, true);
  current = null;
  releaseCamera();
  if (id) fetch(`/api/capture/${id}/state`, { ...json({ state: "interrupted", at: new Date().toISOString(), reason: "Page closed; delivery of the final segment is uncertain" }), keepalive: true }).catch(() => {});
});

controls();
refreshLibrary().catch((error) => message(`Could not load the library: ${error.message}`, true));
refreshCoverage().catch((error) => message(`Could not load recording status: ${error.message}`, true));
setInterval(() => refreshCoverage().catch(() => {}), 1500);
