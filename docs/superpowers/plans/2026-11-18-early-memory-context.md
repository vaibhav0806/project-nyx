# Early memory context and short replies

Approved2026-11-18: fetch optional memory candidates alongside image preparation, retain native
further recall, and tune the shared short policy. User also requested replaying their recent
phone-recall trial to check the actual model's reply. Work inline, branch-only commits, no UI.

1. Add regression proof that stored candidates reach the first generation while memory writing
   is blocked, slow/failed lookup does not block ordinary replies, and further recall remains.
2. Reuse PersonalMemory recall without a selection-model call, at most five candidates. One
   bounded independent read lane prevents queued writes from delaying lookup or unbounded reads.
   Start it before the existing image wait; share a250ms lookup budget with that preparation.
   Late/absent candidates are explicitly optional/incomplete. Revalidate sources/corrections and
   historical cutoffs before use; preserve supplied-source dependencies and generation-only context.
3. Replace shared wording rather than expand the prompt. Lead with the useful answer; natural
   attribution, optional early leads and tools for further lookup. Keep <=100 words and Luna6.
4. Run targeted/full checks. Replay the user's recent question using actual saved memories and
   native model tools, without original chat/answer leakage or full-video upload. Selected replay
   inputs are authorized by this explicit request; keep private artifacts ignored and paid work
   bounded by the existing cumulative$8/per-run guards. Record actual reply, latency and limits.
5. Record findings, commit, and refresh an idle localhost service only after checking capture.
   Preserve all data and active recording; do not activate hardware or open a new PR.
