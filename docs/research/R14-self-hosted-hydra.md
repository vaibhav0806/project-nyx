# R14 — Isolated self-hosted Hydra trial

Date: 2026-11-15 (local); server logs report UTC November 14. Owner: inline agent.
Status: isolation and vector persistence verified; usable server-side vector ranking not established.
Decision affected: whether this deployment should replace Nyx's existing vector retrieval.

## Method and isolation

The user authorized the provided SSH key/host and asked for separate Nyx storage. Read only
the existing Hydra container's deployment metadata and available host memory; no application
records, logs or credentials from the other project were read. Created a dedicated `nyx-hydra`
container, internal Docker network, `nyx-hydra-data` volume and fresh token, with graph/namespace
`nyx`. There is no shared source volume or other project's storage credential.

Reused the already-present pinned image, digest
`ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880`.
Its build reports commit `916637477f3f34766b4905b270bd4292109d77e6`, Rust 1.99.0,
branch v0.4.0. Host Linux/Python 3.12, about 3.8 GiB RAM with roughly 2 GiB available before
creation. Nyx's container is limited to 512 MiB, 0.5 CPU and 128 PIDs; uses local durable storage
and disables usage reporting. It exposes no public host port. Health/query requests ran on the
host against the container's internal bridge address over SSH. The configured loopback publish
did not provide a working route on the internal network; do not document it as usable access.

Initial startup failed because the local store directory did not exist, then because the
image runs as UID/GID 10001 and could not read the new bind-mounted token. Created directories
in the new volume; granted token read access to that service group (0640, enclosing host directory
0700). Only the new Nyx service was restarted. The original application's service was not changed.

## Measured results

| Probe | Result |
| --- | --- |
| Health on internal query endpoint | HTTP 200 |
| Query with invalid token | HTTP 401 |
| Query for a different graph/namespace | HTTP 403 |
| Store synthetic 768-d normalized vector and encoder label | HTTP 200, one-hop MERGE |
| Read vector and encoder back | HTTP 200, one row; exact-value check executed separately |
| Standalone RETURN/scalar query | HTTP 400: row engine requires MATCH ... RETURN |
| Native `vector.similarity.cosine` expression | HTTP 400: parser rejected function |
| MATCH with reduction-based dot product | HTTP 400: RETURN limited to property/count projection |
| Node-only MERGE / MERGE followed by SET | HTTP 400: this execution path requires one-hop patterns |

The successful write used a parameterized one-hop fixture:

```cypher
MERGE (n {id:90001, embedding:$vector, encoder:$encoder})-[:NYX_FIXTURE]->(s {id:90002})
```

Read with `MATCH (n {id:90001}) RETURN n.embedding AS embedding, n.encoder AS encoder`.
Vector input was `[1.0, 0.0, ...]`, 768 values, and encoder label `synthetic-768-v1`.
No inference, provider credit, private media or existing application vectors were needed.
Only these synthetic fixture records occupy the new graph. Tokens stay outside Git/output.

## Recommendation and limits

Compatible existing vectors can be persisted without re-embedding. This does not prove server-side
nearest-neighbor search, useful ranking or performance at Nyx scale. No supported vector retrieval
path was found in the inspected source or successful runtime probes. Keep SQLite retrieval active
and proceed with the coverage/candidate/memory-policy work. Do not fetch all graph vectors and
rank locally while describing that as Hydra vector search. Do not install a substitute database
or migrate private indexes on the strength of this trial.

Any later backend promotion requires a supported similarity/index API, matching encoder fingerprints,
source availability/deletion enforcement and the same fixed-corpus comparison. A dedicated graph
may still be useful for relationships, but that is not a measured benefit from this experiment.

Sources: [public engine](https://github.com/hydra-db/hydradb),
[HTTP usage](https://github.com/hydra-db/hydradb/blob/main/USING-HYDRADB.md), and the actual
read-only metadata/isolated fixture queries above. Live server evidence takes precedence over
assuming the higher-level hosted memory-service documentation describes this image.
