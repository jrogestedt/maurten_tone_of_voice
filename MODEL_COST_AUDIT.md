# Model & Cost-Efficiency Audit

_Audited 2026-06-25. Scope: the Anthropic model usage in `backend/app/` (the review/rewrite/eval path). Pricing and caching facts verified against the current Anthropic model catalog._

## TL;DR

The setup is **well-architected and cost-conscious already**: tiered models (expensive model only for the hard task), prompt caching on the static system prefix with a 1-hour TTL, structured outputs, and bounded `max_tokens`. The big-ticket items are right.

The remaining inefficiencies are second-order:

1. **The prompt cache silently does nothing when few/no reference docs are loaded** — the system prefix falls below the model's minimum cacheable size.
2. **The 1-hour cache TTL costs 2× to write** and only pays off at ≥3 calls/hour; sporadic usage wastes the write premium.
3. **The same system prompt is cached separately per model** (Opus + Sonnet), so its cache-write cost is paid twice.
4. Output tokens — not input — dominate per-call cost, so the cheapest lever is the model tier on the review call, which the eval harness already exists to validate.

---

## What the code does today

| Path | Model | Where | `max_tokens` | Output mode |
|------|-------|-------|-------------|-------------|
| **Review** (semantic/linguistic judgment) | `claude-opus-4-8` | [config.py:14](backend/app/config.py#L14), [anthropic_client.py:70](backend/app/anthropic_client.py#L70) | 2000 | Structured (`ReviewResponse` schema) |
| **Rewrite** | `claude-sonnet-4-6` | [config.py:15](backend/app/config.py#L15), [anthropic_client.py:92](backend/app/anthropic_client.py#L92) | 2000 | Plain text |
| **Eval harness** | inherits Review → `claude-opus-4-8` | [eval/run_eval.py:29](backend/eval/run_eval.py#L29) | 2000 | Structured |

Both calls share a deterministically-built system prompt (persona + active reference docs, capped at `max_context_chars = 60000` chars) and mark it with a **1-hour ephemeral cache** ([anthropic_client.py:34-40](backend/app/anthropic_client.py#L34-L40), [voice.py:71-101](backend/app/voice.py#L71-L101)).

The model IDs are current and correctly chosen for the task split. No timeout risk: `max_tokens=2000` is far below the ~16K non-streaming threshold, so the non-streaming `.create()`/`.parse()` calls are safe.

---

## Pricing reference (per 1M tokens)

| Model | Input | Output | Cache write (1h = 2×) | Cache write (5m = 1.25×) | Cache read (0.1×) |
|-------|------:|-------:|----------------------:|-------------------------:|------------------:|
| Opus 4.8 (review) | $5.00 | $25.00 | $10.00 | $6.25 | $0.50 |
| Sonnet 4.6 (rewrite) | $3.00 | $15.00 | $6.00 | $3.75 | $0.30 |

---

## Cost model of one request

Assume a fully-loaded system prefix near the 60K-char cap ≈ **~15,000 tokens**, a small copy-to-review user message (~400 tokens), and output near the 2000-token cap.

**Review (Opus 4.8), cache warm:**
- System prefix served from cache: 15,000 × $0.50/M = **$0.0075**
- User message (uncached): 400 × $5/M = **$0.002**
- Output 2,000 × $25/M = **$0.050**
- **≈ $0.060 / review** — output is ~83% of the cost.

**Review (Opus 4.8), cache cold (first call / after TTL expiry):**
- System prefix cache **write**: 15,000 × $10/M = **$0.150** one-time
- Same first call therefore ≈ **$0.20**, then ~$0.06 each while warm.

**Rewrite (Sonnet 4.6), cache warm:**
- System prefix cache read: 15,000 × $0.30/M = **$0.0045**
- Output 2,000 × $15/M = **$0.030**
- **≈ $0.035 / rewrite**

Takeaway: **output tokens dominate.** Input-side caching matters most for *latency* and for the cold-write penalty, not for steady-state cost.

---

## Findings & recommendations

### 1. Caching silently no-ops on small contexts — **verify, don't assume**
Prompt caching only engages above a per-model minimum prefix:
- **Opus 4.8: 4,096 tokens**
- **Sonnet 4.6: 2,048 tokens**

With only the default persona prompt (~400 tokens) and few/no reference docs active, the system prefix is **below both minimums**, so the `cache_control` marker is ignored — no error, just `cache_creation_input_tokens: 0` and full-price input every call. The caching pays off only once enough reference docs are loaded to clear ~4K tokens.

**Action:** Log/inspect `usage.cache_read_input_tokens` (the code already logs cache fields at [anthropic_client.py:43-51](backend/app/anthropic_client.py#L43-L51) — good) and confirm it's non-zero in production. If typical deployments run with light reference context, the caching is decorative. Not a bug, but don't count on the savings without checking the logs.

### 2. The 1-hour TTL is a bet on call frequency
1h cache writes cost **2×** input vs **1.25×** for the default 5-minute TTL. Break-even:
- 5m TTL pays off at **≥2 calls** within the window.
- 1h TTL pays off at **≥3 calls** within the hour.

The code comment justifies 1h by "the slow human edit loop between reviews" ([anthropic_client.py:30-31](backend/app/anthropic_client.py#L30-L31)) — reasonable **if** a user does ≥3 reviews/hour. If real usage is sporadic single reviews with >1h gaps, every call pays the 2× cold write and the 1h TTL is strictly worse than 5m.

**Action:** Check the access pattern. If most sessions are bursts of several reviews → keep 1h. If they're one-off reviews spread out → switch to the default 5m TTL (drop the `"ttl": "1h"`) to halve the per-write premium. Make it a config knob if usage varies.

### 3. The system prompt is cached twice (once per model)
Caches are model-scoped. The identical ~15K-token system prefix is cache-written separately for Opus (review) and Sonnet (rewrite). A review+rewrite of the same copy pays **two** cold writes ($0.15 + $0.09) on first touch. Unavoidable given the two-model design, but worth knowing: it roughly doubles the cold-start input cost of a full review→rewrite cycle.

**Action:** None required — it's inherent to tiering. Just don't expect a single shared cache across the two calls.

### 4. Model tier on review is the real cost lever — and you can already test it
Output dominates, and Opus output ($25/M) is **1.67× Sonnet's** ($15/M). Moving the review to Sonnet 4.6 would cut a warm review from ~$0.06 to ~$0.037 (~40% off) — at the cost of judgment quality, which is exactly what review needs Opus for.

You already have `backend/eval/` with a golden set precisely to measure this. **Action:** Run the eval with `anthropic_review_model="claude-sonnet-4-6"` against the golden set. If scores hold, the savings are large and free; if they degrade, you have hard evidence to keep Opus. (Opus 4.7 is the same price as 4.8 — no savings there.)

### 5. `effort` is unset (defaults to `high`) — minor latency/cost lever
Opus 4.8 defaults to `effort: "high"`. The review is a bounded, schema-constrained judgment, not deep reasoning. Setting `output_config={"effort": "medium"}` (or `"low"`) on the review call may reduce latency and token spend with little quality loss — but **must be validated via the eval**, not assumed. Low-priority; the structured-output schema already bounds the output.

### 6. Non-issues (working as intended)
- **Structured output via `.parse()`** ([anthropic_client.py:73-82](backend/app/anthropic_client.py#L73-L82)) is the recommended path; the `output_format=` arg is the supported `.parse()` helper, not the deprecated top-level param. Fine.
- **`max_tokens=2000`** is appropriate for both 3–8-note JSON and short-form copy, and avoids streaming/timeout complexity.
- **Stop-reason guarding** for `refusal`/`max_tokens` ([anthropic_client.py:54-67](backend/app/anthropic_client.py#L54-L67)) is correct and prevents opaque parse failures.
- **Deterministic system-prompt assembly** ([voice.py:79-83](backend/app/voice.py#L79-L83)) is what makes caching possible at all — the cache is a prefix match, so this ordering is load-bearing. Good.

---

## Priority order

1. **Confirm caching actually engages** in production (finding #1) — check `cache_read_input_tokens` in logs.
2. **Match the cache TTL to real call frequency** (finding #2) — 5m if usage is sporadic.
3. **Eval Sonnet vs Opus for review** (finding #4) — the single biggest potential saving, and you already have the harness.
4. Optionally tune `effort` (finding #5), validated by the same eval.
