# Personal-memory vector retrieval

Approved in conversation on 2026-11-18. One continuous conversation supplies recent
context; durable saves may finish later. No immediate read-after-write guarantee is required.

Keep source-linked records in `memories`; add a linked sqlite-vec `vec0` table using
the existing embeddings. Filter timestamps, replaced records and withdrawn sources;
validate only retrieved records and their dependencies. Keep reranking optional.
Background writes remain ordered. Recall does not wait for background interpretation.
Unresolved background saves remain internal, preserving input without guesses or questions.

Approaches: retaining Python ranking repeats corpus/vector work; SQL scalar distance is
a useful baseline; selected vec0 moves KNN into the existing SQLite extension. No external
database, provider/model change, UI change, main change, hardware or private upload.
Migration is additive, fingerprint/dimension separated, with original vectors/media intact.

Verify source/correction/as-of semantics, migration/restart, ordering and no-wait recall,
candidate-bounded validation, scaling and offline replay of the user's saved phone trial.
