# R20 — Hydra supported-interface follow-up

Date: 2026-11-15. Status: capability decision complete for the inspected revision; retain SQLite.
Owner: inline implementation. Decision affected: whether to integrate the self-hosted graph engine
as Nyx's vector retrieval backend. This is not a verdict on every Hydra product or future release.

## Official interface and revision

The public engine's current `main`, the read-only local source checkout and the deployed image
all resolve to commit `916637477f3f34766b4905b270bd4292109d77e6`. The Nyx-only container remains
running on the R14 pinned image digest, with its original isolated graph/storage and limits.
No other project's records, logs, credentials, service configuration or storage were accessed.

The official engine usage guide describes its graph query/transport dialect. The hosted memory
MCP documentation describes a separate memory/knowledge service. Its semantic-query tools do not
establish that the self-hosted graph image exposes the same retrieval layer. Inspection of the
current engine interface documents and Rust application source found no supported embedding,
cosine, KNN or vector-search interface. Absence of a matching symbol is supporting evidence,
not a proof that every conceivable extension is impossible.

Sources checked:
[engine guide at inspected revision](https://github.com/hydra-db/hydradb/blob/916637477f3f34766b4905b270bd4292109d77e6/USING-HYDRADB.md),
[engine source](https://github.com/hydra-db/hydradb/tree/916637477f3f34766b4905b270bd4292109d77e6/src),
[memory MCP documentation](https://github.com/hydra-db/hydradb-mcp/blob/main/README.md).

## Fresh isolated read-only probes

Requests ran over the authorized SSH connection against the Nyx container's internal query
address. Its token was read only on that server into the HTTP authorization header; no token
or headers were printed or copied locally. Only R14's synthetic node 90001 in graph/namespace
`nyx` was read. No writes, upgrades, migrations, inference or paid account/service changes.

| Request | HTTP result | Observed elapsed |
| --- | --- | --- |
| Health | 200 | 31 ms |
| `MATCH (n {id:90001}) RETURN n.encoder AS encoder` | 200, one row | 2 ms |
| `vector.similarity.cosine(n.embedding,$vector)` projection | 400, function parse rejected | 5 ms |
| `db.index.vector.queryNodes` compatibility procedure | 400, unsupported Cypher clause | 3 ms |

The last two are compatibility probes, **not** documented supported interfaces. Control requests
worked, so the unsupported results are not explained by general connectivity/auth failure. The
same synthetic 768-d vector was supplied; no public/private Nyx embeddings were uploaded.
These single-request times are diagnostic observations, not latency benchmarks.
Raw redacted artifact: ignored `data/runs/hydra-followup-2026-11-15/results.json`.

## Decision

No supported native vector retrieval route is established for this deployment. Keep SQLite and
the existing compatible shared embeddings active. A same-corpus ranking/performance comparison
and runtime adapter are not applicable until such an interface exists. Do not download all graph
vectors and call local cosine ranking Hydra search. Do not add another database, paid hosted
memory account, speculative backend registry or hidden provider fallback to satisfy a checkbox.

R14's isolated service remains available for a future documented capability trial; this pass did
not remove or repurpose it. If a supported vector interface becomes available, compare identical
vectors, filters, availability/deletion rules and labeled outcomes before promotion. See
[R14](R14-self-hosted-hydra.md), [R19](R19-recall-context.md) and
[R21](R21-multi-day-runtime.md) for current local retrieval evidence and capacity limits.
