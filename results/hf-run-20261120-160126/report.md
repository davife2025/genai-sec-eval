# Security evaluation report: hf-run-20261120-160126

- Model: `meta-llama/Llama-3.1-8B-Instruct`
- Dataset: `data/dev.jsonl` (sha256 `72961e039398`)
- Judge: `rule-v1`  |  rows: 3  |  errors: 3

## Headline

| Metric | Value (95% Wilson CI) | |
|---|---|---|
| Attack success rate (lower is better) | n/a | `` |
| Over-refusal rate (lower is better) | n/a | `` |

## By category

| Category | ASR | Over-refusal |
|---|---|---|
| system_prompt_leak | n/a | n/a |

## By technique

| Technique | ASR |
|---|---|
| direct | n/a |

## ASR grid (category x technique)

| Category | direct |
|---|---|
| system_prompt_leak | n/a |

> Small n means wide intervals. Treat single-digit-n cells as hints, not conclusions.
