# Subgraph Runner — Meta Skill (Scheme F layer A)

## When to Use

When a short-drama (or other) stage declares `subgraph_refs` and you must execute a composable subgraph IR instead of improvised tool chains.

## Protocol

### 1. Load

- Resolve path from pipeline/storyboard `subgraph_refs` or project override `projects/<name>/subgraphs/`.
- Run `subgraph_validate` tool before execution.

### 2. Walk

For each ready node in topological order (respecting edge `when` via `lib.workflow_expr`):

| type | Action |
|------|--------|
| `tool` | Bind `params` with expressions; `registry` tool `.execute()` |
| `agent` | Read `skill` markdown; produce declared output artifact keys into run context |
| `router` | Evaluate routes; set `chosen_provider` / port on context |
| `human_gate` | Checkpoint `awaiting_human`; stop until approved |
| `code` | JSONPath-only transforms from `lib.workflow_expr` (no arbitrary Python) |

Write progress to `projects/<name>/subgraph_runs/<run_id>.json`.

### 3. Ports

Follow `success` / `failure` / `rework` edges. Rework loops must honor `max_reworks` on the subgraph.

### 4. Map boundary

Do **not** implement shot Map inside subgraphs. Fan-out stays in `shot_job_manager`.

### 5. NL patch

Natural-language graph edits produce an IR diff → validate → write override file. Do not rewrite main-chain stage lists without explicit advanced-compile confirmation.
