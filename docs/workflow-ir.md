# Workflow IR (Scheme F)

OpenMontage short-drama uses a **hybrid** programmable model:

| Layer | Mechanism | Location |
|-------|-----------|----------|
| Main chain (B) | `pipeline_defs/*.yaml` stages + director skills | `pipeline_defs/short-drama.yaml` |
| Subgraphs (A) | JSON Workflow IR, agent-executed | `workflow_defs/subgraphs/*.workflow.json` |
| Shot Map (C-lite) | File ledger queue | `shot_job_manager` → `shot_jobs.json` |

## Subgraph document

Validated by `schemas/workflows/subgraph.schema.json` and `subgraph_validate` tool.

Node types: `agent`, `tool`, `router`, `human_gate`, `code` (JSONPath/expression assigns only).

**No top-level `map` node** — fan-out is owned by `shot_job_manager`.

Edges: `default | success | failure | rework | approve | reject` with optional `when` expressions (`lib/workflow_expr.py`).

## Expressions

- Interpolation: `"dur={{shot.duration_sec}}"`
- Raw bind: `"{{shot.duration_sec}}"` → number
- Conditions: `"{{drama_qa_report.critical_count}} > 0"`

Arbitrary Python `eval` is forbidden.

## Presets

- `video-router` — shot_intent → provider
- `keyframe-i2v-qa` — keyframe → I2V → QA (+ rework)
- `audio-pack` — TTS + optional lip sync
- `fallback-escalate` — provider fallback chain

## Execution

Directors follow `skills/meta/subgraph-runner.md`. Validate before run. Persist node progress under `projects/<name>/subgraph_runs/`.

## Lab compile (main chain)

`lib/pipeline_compile.project_main_chain_patch` applies restricted patches (human gates, tools, subgraph_refs, reorder). Inventing new stages requires editing `pipeline_defs`.
