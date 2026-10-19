import base64
from datetime import datetime, timedelta
from html import escape
from pathlib import Path


def write_gallery(query, results, root: Path, destination: Path):
    cards = []
    for result in results:
        seconds = result["offset_seconds"]
        minutes, remainder = divmod(seconds, 60)
        timestamp = f"{int(minutes):02}:{remainder:06.3f}"
        image = base64.b64encode((root / result["thumbnail"]).read_bytes()).decode()
        video = (root / result["video_path"]).resolve().as_uri() + f"#t={seconds}"
        captured = "Capture time unknown"
        if result["recorded_at"]:
            captured = (
                datetime.fromisoformat(result["recorded_at"]) + timedelta(seconds=seconds)
            ).isoformat()
        cards.append(f'''<article>
          <a href="{escape(video, quote=True)}"><img src="data:image/jpeg;base64,{image}"
             alt="Candidate frame at {timestamp}" /></a>
          <div class="detail"><strong>{timestamp}</strong><span>Similarity {result["similarity"]:.3f}</span></div>
          <p>{escape(result["name"])}<br><small>{escape(captured)}</small></p>
          <a class="open" href="{escape(video, quote=True)}">Open source clip ↗</a>
        </article>''')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nyx · {escape(query)}</title>
<style>
:root {{color-scheme:light;--ink:#24352d;--muted:#64736b;--paper:#f5f4ee;--line:#d9ded4}}
* {{box-sizing:border-box}} body {{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,sans-serif}}
main {{max-width:1180px;margin:auto;padding:44px 28px 70px}} header {{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:16px}}
header b {{font-size:23px}} header span,small {{color:var(--muted)}} h1 {{font:normal clamp(30px,5vw,52px)/1.15 Georgia,serif;margin:36px 0 14px;overflow-wrap:anywhere}}
.intro {{max-width:70ch;color:var(--muted);margin-bottom:32px}} .grid {{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:30px 22px}}
article {{min-width:0;border-bottom:1px solid var(--line);padding-bottom:20px}} img {{width:100%;aspect-ratio:4/3;object-fit:contain;background:#e8e9e1;border-radius:4px}}
.detail {{display:flex;justify-content:space-between;gap:8px;padding-top:12px;font:14px ui-monospace,monospace}} article p {{overflow-wrap:anywhere;margin:10px 0}}
a {{color:inherit}} a:focus-visible {{outline:3px solid #4b765d;outline-offset:4px}} .open {{font-size:14px}}
@media(max-width:760px) {{.grid {{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media(max-width:480px) {{main {{padding:24px 18px}} .grid {{grid-template-columns:1fr}} header {{align-items:center;gap:12px}}}}
</style><main><header><b>Nyx</b><span>Local visual memory · retrieval experiment</span></header>
<h1>{escape(query)}</h1><p class="intro">{len(results)} candidate frames, ranked by similarity.
These matches have not been visually verified. Similarity is not a confidence probability;
a missing match does not establish absence. Times identify positions within each clip.</p>
<section class="grid">{"".join(cards) or "<p>No indexed frames matched the search filters.</p>"}</section>
</main></html>""",
        encoding="utf-8",
    )
    return destination.resolve()
