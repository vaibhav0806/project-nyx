# Working on Nyx

## Household workflow authorization — 2026-11-16

PR2 merged the reliability work at bdb7ad0. The user then authorized engineering the complete
shown-item/remember/later-recall household experience, using existing laptop and public data.
Continue inline on work/memory-reliability from the merged baseline, regular commits and optional
branch-only backups. Keep main/UI/original media untouched. Private recordings stay offline;
cloud developer evaluation uses public/synthetic evidence under the existing $5 TOTAL ceiling.
Do not interpret generic local-video use as permission to upload personal footage or activate
hardware. The household plan/spec defines source-separated full-API workflows and remaining
real-household/acoustic acceptance gates. No automatic new PR or merge was requested.
R29 found an unsafe new saved link in the separated household pipeline. It remains opt-in via
NYX_HOUSEHOLD_REFERENCE_POLICY=separated; default joint retains the merged placement decision plus
an independent ambiguity veto. Do not promote the experimental path based on its higher small-
corpus score. Verified cumulative OpenRouter usage is now$4.73185091/$5; paid tests stopped with
$0.26814909 remaining. Household physical-identity/acoustic/user acceptance remains open.


## Latest authorization — 2026-11-15

The latest user increased the OpenRouter test-key limit to **$5 total**, superseding the prior
$2 cumulative test ceiling for new work. Verified key metadata reports limit5 and prior usage
about1.97. This is not an additional$5 and does not authorize account purchases or uncapped tests.
Continue wake/visual/reliability work on the same branch; all UI/source/main boundaries remain.

The subsequent user request authorized a deeper [visual/spoken reliability pass](docs/superpowers/plans/2026-11-15-visual-spoken-depth.md),
with broader testing and general fixes, never fixture-specific runtime rules. Keep the same
branch-only publication, no-UI, source-preservation and cumulative $2 provider-test boundaries.
R22/R23 record measured failures and rejected alternatives; do not promote vision/wake changes
merely to improve a small fixture score. Real household/acoustic acceptance remains separate.

The user authorized the next [recall/context engineering pass](docs/superpowers/plans/2026-11-15-recall-context.md)
and sustained execution, excluding demo production. Stay on `work/memory-reliability`; make
regular commits. Optional pushes are authorized only to this branch, never main. Main stays stable,
UI stays unchanged, and existing source/spending boundaries remain. Ten days is a search target,
not a requirement to fit continuous ten-day footage inside 1 GiB; measure capacity separately.

The earlier local-branch restriction superseded publication/main execution wording below.
The latest authorization above additionally permits a branch-only backup push; never push main.
Remote main remains the tested `cfe8fa4` foundation. Local main was returned to origin/main after
preserving the new commit on the work branch.

The user explicitly required retaining contributors' UI work and no UI changes in this slice.
Do not edit `src/nyx/web/` or change interface layout, styling, wording or interaction behavior.
Keep implementation in backend/retrieval/storage/experiments and preserve existing UI contracts.

The user approved the [memory reliability design](docs/superpowers/specs/2026-11-15-memory-reliability-design.md)
and implementation order, asked to proceed and requested regular commits. Work inline on the
work branch. The earlier foundation publication is complete; the latest branch-only authorization
controls all new work. They authorized SSH access to the teammate's Hydra host and
separate Nyx storage/service isolation, preserving the other project. Reuse compatible existing
vectors; do not assume the graph deployment supplies vector retrieval or embedding inference.
Shared embedding alternatives are conditional on measured accuracy. Preserve prior provider-budget,
public/synthetic developer-test, source-preservation and 1 GiB stop-without-delete boundaries.

## Latest authorization — 2026-10-29

The user authorized merging the companion MVP (completed via PR #1), then working
directly on main on bounded compression/retention MVP work. New recordings may
use a tested lower-bitrate/frame-rate profile. Continuous coverage, existing files
and the 1 GiB stop-without-delete rule remain. No automatic expiry or destructive
recompression. This supersedes older no-merge language for the completed merge;
future publication follows the user's actual instruction.


## Current authorization

On 2026-10-28 the user explicitly approved cloud inference as the primary MVP path,
removing the local LLM/VLM stack, cloud multimodal embeddings with a rebuilt development
index, and OpenRouter activated STT/TTS. Local wake recognition, activity filtering,
small object detection and recording/storage remain. This supersedes earlier local-only
visual inference and Sarvam-only boundaries. Selected images/sequences and activated
speech may go to OpenRouter/model providers; developer tests still use synthetic/public
fixtures, never real camera/microphone hardware. The supplied key has a $2 test limit.
Keep credentials ignored and backend-only. Preserve saved recordings. Local commits
are authorized; no push or merge.

On 2026-10-20 the user authorized autonomous implementation and local experiments for a conversational tool-using agent, adaptive continuous observation, and a next-departure reminder (for example, taking a water bottle when leaving). They authorized small public-video/model downloads with attention to limited disk, then coherent local commits and explicitly **no push**. This supersedes the earlier later-milestone boundary for this bounded M5 event-request slice only. General personal recall, time-based reminders and hardware purchases remain later work. Keep developer tests synthetic or permitted offline replay; do not open real camera/microphone hardware or upload private visual media during developer tests. See [the agent/observation plan](docs/superpowers/plans/2026-10-20-agent-observation.md) and [R8 findings](docs/research/R8-companion-loop.md). Work inline; the user has not authorized subagents.

The user reviewed the documentation and explicitly asked to continue working on 2026-10-19. **M1 retrieval, continuous recording/background search, M2 history controls, M3 temporal retrieval/visual answers and M4 Sarvam voice are authorized.** The user explicitly requested M3 on 2026-10-19; this supersedes the earlier later-milestone boundary for M3 only. The user requested publishing the working automatic-indexing slice and proceeding with the remaining milestone work on 2026-10-19, then explicitly requested all current work be pushed to GitHub. This authorizes publishing the M2 history controls, M3 visual answers and M4 voice snapshot to `main`; raw data and credentials stay local. The user selected a 1 GiB saved-video budget: stop at the limit, preserve existing clips, never automatically delete them. The user explicitly wants automatic camera/microphone startup with the app and wake-by-name activation, including a future hardware product, like Alexa/Siri. A configured browser page requests permissions and starts automatically; process-only startup cannot control browser hardware. Automated developer verification must use synthetic camera/microphone inputs. Sarvam may receive activated spoken questions and synthesize answers; idle audio and all visual media remain local. Outreach, purchases, and later product milestones remain separately scoped. See the [continuous recording plan](docs/superpowers/plans/2026-10-19-continuous-recording.md); it supersedes the earlier manual-only implementation boundary.

Design approval and implementation authorization are separate. Once the user authorizes an approved milestone, complete its necessary work without asking for permission at every reversible step.

## Read before acting

1. Read `README.md` and `docs/decisions.md` for current status.
2. Read `docs/design.md` and `docs/scope.md` for intent and boundaries.
3. Read `docs/architecture.md`, `docs/repository.md`, and the relevant entry in `docs/milestones.md` before implementation.
4. Read relevant findings under `docs/research/` before choosing a model or changing product direction.

Explicit user instructions take precedence. If documents disagree, identify the conflict and resolve it against the latest user decision; update the affected documents together. Research findings are evidence, not automatic approval to change scope.

## Engineering

- Question the approach before executing. Read existing code and match its style.
- Prefer simple, readable solutions. Avoid speculative abstractions, provider registries, microservices, and extra infrastructure.
- Keep one Python application in `src/nyx/`; split modules when responsibilities require it. Follow `docs/repository.md`.
- Create only the folders and files needed by the current task. The proposed tree is not a scaffolding checklist.
- The current baseline has a real `src/nyx/` package, locked optional vision dependencies, deterministic tests, and a separately run semantic benchmark. Read the README commands and R3 findings; do not equate the public-image benchmark with household accuracy.
- Keep changes scoped. Run checks appropriate to actual changes. For documentation, check links and consistency; no dependency installation is needed.
- Use meaningful tests for persistence, retrieval ordering, evidence attribution, failure handling, and action replay. Keep real-model evaluation separate from deterministic tests.

## Product and evidence

- Preserve the older-adult independence mission; the laptop scene is a development setting.
- Keep recordings, sampled observations, retrieved candidates, and verified findings distinct.
- A nearest-neighbor result is a candidate, not proof that an object is present.
- Distinguish current evidence, historical evidence, assistant conversation, and user-provided memory.
- Preserve recording timestamps, clip offsets, model/version information, and coverage gaps. Never substitute import time for an unknown capture time.
- Report uncertainty and failed capture honestly. Never infer that an event did not happen simply because it was not indexed.
- Keep reminder scheduling/delivery/acknowledgement separate. Report overdue delivery after sleep or restart truthfully.
- Follow the recording, retention, deletion, and identity boundaries in `docs/scope.md`.

## Research and experiments

- Use the question IDs and evidence format in `docs/research/README.md`.
- Record sources, dates, machine/runtime/model versions, method, results, failure examples, limitations, and recommendation.
- Label claims as measured, source-reported, inferred, or proposed. Do not turn manufacturer benchmarks into laptop results.
- Experiments must state how their result would change a decision. Keep research scripts separate from application code.
- A benchmark request does not authorize capturing people, contacting interviewees, uploading household footage, or spending on a hosted service. Honor the scope the user actually gave.
- Write anonymized findings into Git; keep raw personal material and credentials out.

## Collaboration and authorship

- Do all work inline. Spawn subagents only when the user explicitly asks for them; skills or project complexity do not override this.
- Human research assignments can be documented here. Send no messages or invitations without explicit authorization.
- Never add `Co-Authored-By` trailers or use `git commit --author`. Let Git configuration provide authorship.
- Do not commit, push, open a PR, or publish these drafts merely because a milestone is marked ready for review. Follow the user's actual request.
- When asked to access existing Chrome, first read `/Users/vaibhav/.codex/skills/browser-access/SKILL.md` and use its read-only process discovery. Report tab discovery and full page control separately.

## Keeping progress accurate

Use `docs/milestones.md` as the status source. Update it with evidence when work actually completes. Record a changed architectural choice in `docs/decisions.md`, then update the affected design/architecture/scope documentation. Report what changed, how it was checked, and material unknowns concisely.
