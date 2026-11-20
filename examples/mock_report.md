# Security evaluation report: partial-20261119-105008

> **Sample output from the offline mock model, not a real LLM.** It only shows what a report looks like.

- Model: `mock`
- Dataset: `data/dev.jsonl` (sha256 `72961e039398`)
- Judge: `rule-v1`  |  rows: 100  |  errors: 0

## Headline

| Metric | Value (95% Wilson CI) | |
|---|---|---|
| Attack success rate (lower is better) | 75.0% (65-83%, n=80) | `███████████████░░░░░` |
| Over-refusal rate (lower is better) | 30.0% (15-52%, n=20) | `██████░░░░░░░░░░░░░░` |

## By category

| Category | ASR | Over-refusal |
|---|---|---|
| policy_bypass | 75.0% (53-89%, n=20) | 40.0% (12-77%, n=5) |
| secret_exfiltration | 75.0% (53-89%, n=20) | 60.0% (23-88%, n=5) |
| system_prompt_leak | 75.0% (53-89%, n=20) | 0.0% (0-43%, n=5) |
| unauthorized_action | 75.0% (53-89%, n=20) | 20.0% (4-62%, n=5) |

## By technique

| Technique | ASR |
|---|---|
| direct | 0.0% (0-16%, n=20) |
| encoded | 100.0% (84-100%, n=20) |
| indirect | 100.0% (84-100%, n=20) |
| roleplay | 100.0% (84-100%, n=20) |

## ASR grid (category x technique)

| Category | direct | encoded | indirect | roleplay |
|---|---|---|---|---|
| policy_bypass | 0% (n=5) | 100% (n=5) | 100% (n=5) | 100% (n=5) |
| secret_exfiltration | 0% (n=5) | 100% (n=5) | 100% (n=5) | 100% (n=5) |
| system_prompt_leak | 0% (n=5) | 100% (n=5) | 100% (n=5) | 100% (n=5) |
| unauthorized_action | 0% (n=5) | 100% (n=5) | 100% (n=5) | 100% (n=5) |

> Small n means wide intervals. Treat single-digit-n cells as hints, not conclusions.
