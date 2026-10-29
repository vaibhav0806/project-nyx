"""Replay a permitted short WebM through browser recording; never opens hardware."""

import argparse
import base64
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--source", type=Path, required=True, help="Permitted short WebM, ideally 10 seconds"
)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
source = args.source.resolve()
out = args.output
out.mkdir(parents=True, exist_ok=False)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.route(
        "http://fixture.test/video.webm",
        lambda route: route.fulfill(path=str(source), content_type="video/webm"),
    )
    page.goto("about:blank")
    results = []
    for name, rate, fps in [("baseline", 2500000, 30), ("compact", 1000000, 15)]:
        r = page.evaluate(
            """async ({rate,fps}) => {
   const video=document.createElement('video');video.src='http://fixture.test/video.webm';video.muted=true;video.crossOrigin='anonymous';
   await new Promise((resolve,reject)=>{video.onloadeddata=resolve;video.onerror=reject});
   const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;const ctx=canvas.getContext('2d');
   const stream=canvas.captureStream(fps);const recorder=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8',videoBitsPerSecond:rate});const chunks=[];
   recorder.ondataavailable=e=>chunks.push(e.data);const stopped=new Promise(resolve=>recorder.onstop=resolve);
   ctx.drawImage(video,0,0);recorder.start();const timer=setInterval(()=>ctx.drawImage(video,0,0),1000/fps);await video.play();await new Promise(resolve=>video.onended=resolve);clearInterval(timer);recorder.stop();await stopped;stream.getTracks().forEach(t=>t.stop());
   const blob=new Blob(chunks);const data=await new Promise(resolve=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.readAsDataURL(blob)});
   return {data,bytes:blob.size,width:canvas.width,height:canvas.height,requested_bps:rate,fps};
  }""",
            {"rate": rate, "fps": fps},
        )
        (out / (name + ".webm")).write_bytes(base64.b64decode(r.pop("data")))
        r["name"] = name
        results.append(r)
        print(r, flush=True)
    (out / "encode.json").write_text(
        json.dumps({"browser": browser.version, "results": results}, indent=2)
    )
    browser.close()
