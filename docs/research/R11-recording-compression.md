# R11 — Recording compression MVP

Date: 2026-10-29. Decision: use a lower bitrate and frame rate for new continuous
recordings; retain old recordings and 1 GiB stop-without-delete policy.

## Method and results

User-authorized saved 10-second glasses footage was replayed through a canvas into
Chromium 156.0.8078.4 MediaRecorder. No webcam/microphone opened. Compare VP8 at
720p with 2.5 Mbps/30 fps versus 1 Mbps/15 fps. Browser encoding requests are targets;
actual encoded bitrate varies. This is a replay of already compressed video,
not an actual-camera quality or battery benchmark.

| Profile | Size |
| --- | ---: |
| Previous bitrate / 30 fps | 2,521,312 bytes |
| Compact bitrate / 15 fps | 642,606 bytes |

Measured reduction: 74.5% on this clip. ffprobe confirmed the compact output is
VP8, 1280x720, 9.968 seconds, with reported rate approximately 15 fps. Duration and
continuous coverage remain; frames are temporally sampled at lower frame rate.

Gemini 3.5 Flash-Lite independently judged the glasses visible in both profiles
at replay offset 0.3 seconds, identifying their held position. This is one object
at one offset, not proof of unchanged household accuracy. Fast movement, distant
small objects, low light and other browsers remain unmeasured. Preserve 720p and
avoid more aggressive compression until tested on those cases.

At the nominal 1 Mbps target, 1 GiB is roughly 2.4 hours before overhead; actual
capacity varies and the measured clip compressed further. This still does not
support days of continuous footage. No original files were changed or deleted,
no retention window enabled and no storage budget increased.

Raw clips and results: ignored `data/runs/compression/`. Reproduce browser encoding
with `uv run --no-sync python experiments/capture_compression.py --source <permitted-short.webm> --output <new-output-directory>`.
The quality check makes two explicitly authorized selected-frame cloud requests;
encoding is entirely local. It uses no new model weights or background service.

Sources: [MediaRecorder options](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/MediaRecorder)
and [frame-rate constraints](https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/frameRate).
Targets are not a byte quota; backend byte admission remains authoritative.
