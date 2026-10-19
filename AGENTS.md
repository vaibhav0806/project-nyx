# Working on Nyx

## Current authorization

On 2026-10-20 the user authorized autonomous implementation and local experiments for a conversational tool-using agent, adaptive continuous observation, and a next-departure reminder (for example, taking a water bottle when leaving). They authorized small public-video/model downloads with attention to limited disk, then coherent local commits and explicitly **no push**. This supersedes the earlier later-milestone boundary for this bounded M5 event-request slice only. General personal recall, time-based reminders and hardware purchases remain later work. Keep developer tests synthetic or permitted offline replay; do not open real camera/microphone hardware or upload visual media. See [the agent/observation plan](docs/superpowers/plans/2026-10-20-agent-observation.md) and [R8 findings](docs/research/R8-companion-loop.md). Work inline; the user has not authorized subagents.

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
