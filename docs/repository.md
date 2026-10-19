# Repository structure

Status: working structure; M1 implementation started after the user requested it. Create implementation folders only when their milestone needs them. This is one product repository, not a collection of independently deployed services.

## Proposed layout

```text
project-nyx/
├── README.md                 # Entry point, real project state, eventual run commands
├── AGENTS.md                 # Rules for coding/research agents
├── pyproject.toml            # Python dependencies and tooling, finalized during setup
├── uv.lock                   # Reproducible Python dependency resolution
├── .gitignore
├── docs/
│   ├── design.md             # Mission, audience, workflows, product principles
│   ├── scope.md              # Included behavior, current slice, later work
│   ├── architecture.md       # Components, data flow, evidence and runtime contracts
│   ├── repository.md         # This layout and contribution conventions
│   ├── milestones.md         # Progress and acceptance evidence
│   ├── decisions.md          # Decision status and rationale
│   └── research/
│       ├── README.md         # Research board, briefs and findings format
│       └── <question-id>-<topic>.md
├── src/
│   └── nyx/
│       ├── cli.py            # Current index/search/list/doctor entry point
│       ├── report.py         # Current self-contained candidate gallery
│       ├── app.py            # API and application lifecycle
│       ├── capture.py        # Frame extraction and decoded source offsets
│       ├── recording.py      # Durable capture sessions, uploads, budget and recovery
│       ├── perception.py     # Background image/text encoder
│       ├── verification.py   # On-demand local VLM and strict judgment parsing
│       ├── answers.py        # Temporal history checks and evidence-linked answers
│       ├── retrieval.py      # Search, temporal filters and evidence selection
│       ├── memory.py         # SQLite schema, persistence and source lifecycle
│       ├── voice.py          # Cloud conversation and tool exchange
│       ├── reminders.py      # Durable reminder lifecycle
│       └── web/              # Packaged plain HTML/CSS/JS manual interface
├── experiments/
│   └── <topic>/
│       ├── README.md         # Question, method, exact command, result location
│       └── run.py            # Small reproducible experiment
├── tests/
│   ├── test_<component>.py   # Deterministic behavior tests
│   └── fixtures/            # Small synthetic or redistributable fixtures
└── data/                     # Ignored local artifacts; never a source dependency
    ├── recordings/
    ├── frames/
    ├── db/
    └── runs/                 # Raw metrics and experiment outputs
```

The module list describes ownership boundaries. Start with the modules the approved slice needs, then split only when code responsibilities justify it. Package/build metadata and exact commands are finalized with the first implementation slice.

## What belongs where

| Material | Location |
| --- | --- |
| A product requirement or changed experience | `docs/design.md` and/or `docs/scope.md` |
| A selected technical direction and its tradeoff | `docs/decisions.md`, then `docs/architecture.md` |
| A bounded research question, interview synthesis, competitor study, or model comparison | `docs/research/<question-id>-<topic>.md` |
| Runnable exploratory code | `experiments/<topic>/` |
| Reusable runtime behavior | `src/nyx/` |
| Browser code | `src/nyx/web/` (packaged with the application) |
| Repeatable automated assertions on behavior | `tests/` |
| Raw recordings, databases, vectors, large outputs, and personal research notes | Ignored `data/` or an explicitly chosen private location |
| Downloaded model weights | Normal external model cache or ignored local `models/`; document the location |

An experiment should not be imported by production code. When its approach is selected, move the smallest useful behavior into the application with appropriate tests. Avoid a second copy of the runtime under experiments.

## Research and experiment conventions

- Name research by question ID, for example `R1-daily-workflows.md`; use its front matter to record owner, status, and date.
- Name experiments by task, for example `image-text-retrieval/` or `jepa-event-selection/`, rather than naming the whole design after one model.
- Every experiment records checkpoint/revision, runtime, device, preprocessing, dataset, command, and metrics. Share the same test inputs when comparing models.
- Commit small anonymized tables and representative permitted examples. Keep raw artifacts local, with a documented reference and digest when reproducibility needs one.
- Use a deterministic test suite without downloading weights or contacting providers. Real-model benchmarks run separately and are reported as such.

## Current implementation

The interrupted dependency/test drafts have been reconciled with `src/nyx/`. The package now contains `capture.py`, `perception.py`, `memory.py`, `retrieval.py`, `report.py`, and `cli.py`. `tests/test_nyx.py` exercises the real storage/import/search boundaries and uses a deterministic encoder double only at the external inference boundary.

`experiments/image-text-retrieval/` runs the real pinned model and optional crop comparison separately. `app.py` and packaged `src/nyx/web/` implement continuous local recording, automatic indexing and interactive candidate search. `recording.py` owns the durable capture journal; `tests/test_recording.py` covers admission, storage and recovery. Packaging the plain assets avoids a separate frontend build or source-tree dependency; move to a separate frontend only if actual complexity warrants it. `tests/test_app.py` covers API behavior; opt-in `tests/browser_smoke.py` checks the real model and browser with synthetic camera frames. M3 uses `verification.py` and `answers.py` for local model-checked temporal answers; `voice.py` owns local wake recognition, Sarvam and conversation storage; `web/voice.js` and `web/audio-worklet.js` own hands-free audio. Reminders have not been implemented. The HTML gallery remains a separate generated artifact.

Earlier files under `docs/superpowers/` now point to the canonical documents above. New project documentation belongs in the named `docs/` locations; avoid competing designs or milestone lists.


## Companion/event additions — 2026-10-20

The actual package now also contains `agent.py` (bounded tool decisions), `attention.py` (cheap adaptive selection), `observation.py` (ephemeral live sequences), `intentions.py` (durable next-departure and delivery state), and `companion.py` (API/tool integration). `web/companion.js` is packaged with the existing plain assets. General `reminders.py` scheduling remains a proposed ownership boundary, not an implemented module.

`tests/test_agent.py`, `test_attention.py`, `test_observation.py`, `test_intentions.py` and `test_companion.py` exercise behavior with deterministic inference boundaries. `tests/companion_browser_smoke.py` uses generated media; real local experiments live in `experiments/companion/`. Follow [its README](../experiments/companion/README.md) for source/license and storage limits. Local databases now also include `intentions.sqlite3`; raw media and model outputs remain ignored.
