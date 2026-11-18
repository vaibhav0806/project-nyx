# R36 — Persistent message relay calls

Date: 2026-11-18. Owner: inline implementation. Status: deterministic validation;
manual telephony acceptance pending. Decision: add Bolna as a narrow phone-call tool,
keeping the existing local browser voice pipeline.

## Evidence and method

Source-reported: Bolna's [call API](https://www.bolna.ai/docs/api-reference/calls/make)
accepts agent ID, recipient and per-call variables, returning an execution ID.
Its [quickstart](https://www.bolna.ai/docs/quickstarts/api) documents polling and warns
that call-disconnected precedes finalized transcripts/summary. Reviewed 2026-11-18.

Observed: authenticated account/agent reads succeeded. No owned phone numbers were
returned by the phone-number inventory; this does not establish whether a verified
trial recipient exists. A dedicated relay agent was created using the account's
existing provider settings. Read-back verified the exact relay prompt and enabled
call summaries. Other agents were not modified. No calls were placed.

Local validation uses Python 3.12, the repository's locked dependencies and synthetic
provider outcomes (`tests/test_calling.py`). Tests cover contact validation,
request idempotency and contact snapshots, uncertain/rejected submissions, restart
during submission, waiting for final results, interrupted notification replay,
voice playback acknowledgement and typed display acknowledgement. No hardware or
private media is used. Account credentials and contact information remain ignored.
Final checks: 523 tests passed in 37.24 seconds; Ruff, formatting, JavaScript syntax
and local documentation-link checks passed. The configured local endpoint was
verified after restart; the user-supplied favorite was saved without placing a call.

## Limits and recommendation

Integrate as an immediate relay prototype. Manual tests must establish caller-number
availability, verified-recipient eligibility, actual hangup behavior, accurate message
relay and response summaries, English/Hindi quality and next-interaction delivery.
The initial provider configuration inherits the account's English transcription
setting; bilingual telephone acceptance is not claimed. Provider-side recording and
retention are independent of Nyx's choice not to download audio. Polling resumes
only while Nyx runs. A submission lost before an execution ID is recorded stays
unknown and requires provider review rather than automatic redial.

## Follow-up after manual report feedback

The earlier implementation appended provider summaries after replying from stale
chat context. User screenshots demonstrated contradictory pending/completed claims
and overly formal reports. The updated adapters inject current call results before
generation, keep already-reported outcomes available, and ask the shared model to
convey one pending update within its reply. Tests cover both adapters, interruption
recovery and recipient renaming without confusing different phone numbers. The
Bolna prompt now permits natural requests back to the sender without promising
another call or the sender's actions. Real telephone quality still needs acceptance.

Synthetic cloud probes of the shared production model initially exposed unnecessary
identity caveats; the calling instructions now reserve these for transcript evidence
of a wrong person, voicemail or an unclear speaker. Final synthetic examples produced
brief first-person outcomes, including a request for the sender to call back, without
repeating an older pending status or claiming the summary's alleged delivery occurred.
These probes sent invented dialogue only and placed no calls. Conversational quality
remains model-dependent; completion receipts track successful output, not proof that
the user understood it. The backend was restarted to load instruction version 11.

Post-fix full suite: 524 tests passed in 35.06 seconds; lint/format checks passed.

## Closing repetition review — 2026-11-18

Reviewed the six most recent user-operated calls using provider execution transcripts.
Observed endings included unnecessary paraphrases of the recipient's full answer,
formal farewell sequences and an online-presence check after goodbye. One call also
invented a positive statement about the sender's wellbeing. The saved provider
configuration had reverted to the original prompt; the source of that change is
unknown. No automatic prompt writer exists in the application code inspected.

Restored the casual opening and updated the relay instructions: let the recipient
finish, preserve the full response silently, never routinely recap it, acknowledge
once, and repeat the original message only on an explicit request. Also prohibited
inventing facts about the sender. Disabled the provider's check_if_user_online so
silence no longer triggers "are you still there" after closing. Read-back confirmed
the saved prompt and setting; model, voice and telephony configurations were unchanged.
No test calls were placed. Exact acoustic behavior and the provider's eventual
silence-timeout disconnect announcement remain manual acceptance items.

User requested automatic hangup after silence. Changed Bolna hangup_after_silence
from 15 to 10 seconds and verified read-back. Prompt and all other task settings
were unchanged. No test call was placed.

User shortened the silence timeout to 5 seconds, superseding the 10-second setting.
Updated Bolna and verified read-back; other task settings and prompts unchanged.
