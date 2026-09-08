# M4 Reproduction Integrity

M4 turns a successful target compilation into an auditable artifact transaction. The immutable
source IR, task analysis, selection evidence, and final trim evidence remain separate; the
manifest records their identities and outcomes without moving mutable build state into source
nodes.

```text
source repository + recorded build inputs
  -> in-memory parse / graph / analysis / selection / exact lowering
  -> complete rendered bytes and final token recount
  -> strict BuildManifest with canonical build identity
  -> stage and fsync artifact
  -> serialize, stage, and fsync manifest
  -> replace artifact
  -> replace manifest as commit marker
  -> fsync containing directory
```

## Manifest identity

`BuildManifest` schema 1.0 is strict: unknown and missing fields are rejected. Pretty JSON exists
for inspection, while compact canonical JSON defines semantic hashing. `build_id` excludes the
portable operational `source_path` and `artifact_path`, so moving an intact pair or rebuilding to
a new destination does not change semantic identity. It includes the final artifact identity and
all semantic inputs and stored outcomes.

User-supplied `time_anchor` remains semantic because it is an explicit compilation input; no
wall-clock time is sampled. Runtime evidence uses the deterministic baseline sentinel until M5,
not elapsed nondeterministic time.

## Transaction protocol

Artifact and manifest must share a directory. Both new files are fully staged and flushed before
commit. The artifact is replaced first, and the manifest is replaced last as the commit marker.
A pair is valid only if the manifest parses and its stored artifact digest matches. Controlled
failures after the first replacement roll back both paths byte-for-byte; failures before it leave
the old pair untouched. Temporary cleanup is limited to the two explicit staging paths.

This protocol prevents a partial new manifest from claiming success and preserves a prior valid
pair under handled I/O failures. Like other local atomic-replacement protocols, it does not claim
that two directory entries can be replaced in one filesystem syscall or that recovery can defeat
arbitrary hardware loss.

## Verify versus rebuild

Verification is read-only. It validates schema and internal manifest consistency, artifact
existence/digest, tokenizer compatibility, exact final recount, budget, task/policy/pipeline
identities, and—when supplied or still available—the source revision, graph identity, and every
node content hash. It never runs parsing/selection merely to explain stored optimizer evidence.

Rebuild first performs compatibility and verification checks, then recompiles from the recorded
task, policy, target, tokenizer, instructions, budget, time anchor, source revision, and random
seed. It compares semantic manifest fields, final selection order, rendered bytes, exact token
count, and artifact identity. Only an exact match may be committed to the fresh destination.

## Determinism boundary

Generic target rebuilds require only the same source content and compatible compiler semantics.
Model-specific rebuilds additionally require the recorded tokenizer implementation/configuration
and immutable revision to be available locally. Network access is never silently introduced.
An unpinned model revision or changed compiler implementation identity fails compatibility before
destination mutation.
