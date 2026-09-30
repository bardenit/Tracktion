# Plan: Pluggable OCR Providers, Ollama by Default

**Status:** planned, not started. No code changed yet.

**Scope change, 2026-09-30:** this began as a straight replacement of Anthropic with a hardcoded Ollama host. It is now a provider abstraction — Ollama, Anthropic and any OpenAI-compatible endpoint, selectable and configurable from the Settings UI, with Ollama on the local host as the default. Anthropic stays as a configurable option rather than being removed, so OCR survives the Ollama box being offline. Sections written against the original premise have been revised; the accuracy work is unaffected and still applies to the default provider.

**Last verified against the codebase and the Ollama server:** 2026-09-30.

---

## Decisions

| Question | Answer |
|----------|--------|
| Architecture | Pluggable providers, configured in the Settings UI. Not a hardcoded host. |
| Provider types | Ollama native `/api/chat`, Anthropic, and OpenAI-compatible. Generic user-defined HTTP templates were considered and rejected as too much surface for too little gain. |
| Default provider | Ollama at `10.10.10.10:11434`, model `qwen3.5:4b` |
| Granularity | One active provider and model for all four OCR routes. Per-route overrides were considered and deferred. |
| Fallback | **Ask, never silent.** An unreachable provider returns a 503 naming it; the UI offers to retry with another configured provider and the user taps to confirm. A photo never leaves the local network without an explicit action. |
| Why 4b and not 27b/35b | Models do not stay resident indefinitely, so cold load time is on the critical path. 27b (17.7 GB) and 35b (22.6 GB) take too long to load. |
| 9b escape hatch | **Evaluated 2026-09-30, no benefit. Closed.** 9b lost to 4b on four independent comparisons: pump displays (30/40 vs 34/40), fuel receipts, expense receipts, and with thinking enabled. It has not won once. See "Measured accuracy". |
| Model per route | All routes on `qwen3.5:4b`. Latency only truly matters at the pump, where the user is standing outside, so a slower model for receipts was considered — but 9b is less accurate there too, so there is nothing to trade. |
| Prompt | Rewritten. Transcribe-only, explicit decimal-place counts, no arithmetic reconciliation. See "Prompt and schema". |
| Output format | Regex-constrained JSON string schema, not `format: "json"`. See "Prompt and schema". |
| Validation | Range checks in Python, not in the prompt. See "Validation belongs in code". |
| Model selector in UI | No. Fixed model, no user-facing choice. |
| Thinking | Disabled, `think: false`. Measured, not assumed: costs 10-100x latency, produces no accuracy gain, reintroduces parse failures. See "Thinking: measured twice". |
| Transport | Ollama **native** `/api/chat`, not the OpenAI-compatible `/v1` path. See "Transport decision". |
| `keep_alive` | Server default already raised to 10 minutes (`OLLAMA_KEEP_ALIVE=10m`). Requests still pass `keep_alive` explicitly so the app's assumption is visible at the call site and survives a server rebuild. |

### Server capabilities, verified

`GET http://10.10.10.10:11434/api/tags` on 2026-09-30 returned `qwen3.5:4b`:

- family `qwen35`, 4.7B parameters, `Q4_K_M`, 3.4 GB on disk
- context length 262144
- `capabilities: ["completion", "vision", "tools", "thinking"]`

Vision is confirmed by the server itself, not assumed. Note that `thinking` is also a capability, which is why disabling it is mandatory and not cosmetic — see below.

---

## Provider architecture

### Configuration shape

Stored under `integrations.ocr` in `config.json`, which is written `0600` with plaintext secrets — the same treatment the existing S3 secret key and WebDAV password already get. No new class of exposure, but worth stating.

```json
{
  "integrations": {
    "ocr": {
      "active": "ollama-local",
      "providers": [
        {"id": "ollama-local", "type": "ollama", "label": "Local Ollama",
         "base_url": "http://10.10.10.10:11434", "model": "qwen3.5:4b", "api_key": ""},
        {"id": "anthropic", "type": "anthropic", "label": "Anthropic",
         "base_url": "", "model": "claude-sonnet-5", "api_key": "sk-ant-..."}
      ]
    }
  }
}
```

### Adapter interface

`_get_client()` is replaced by a provider lookup returning an adapter:

```python
def scan(self, image: bytes, media_type: str, prompt: str, schema: dict) -> dict
```

Each route passes its prompt and schema; the adapter decides how to express them.

| | Ollama | Anthropic | OpenAI-compatible |
|---|---|---|---|
| Endpoint | `POST {base}/api/chat` | SDK `messages.create` | `POST {base}/chat/completions` |
| Image | `images: [b64]` | `source: {type: base64, ...}` | `image_url` with a `data:` URI |
| Schema | `format: <schema>` | **none** — prompt only | `response_format: json_schema` |
| Disable thinking | `think: false` | n/a | n/a |
| Keep resident | `keep_alive: "10m"` | n/a | n/a |
| Token cap | `options.num_predict` | `max_tokens` | `max_tokens` |

**Structured output does not port, and this is the single most important consequence of going multi-provider.** Every measured result in this document depends on Ollama's `format` parameter — it is what eliminated the decimal drops and the type instability. Anthropic has no equivalent; the adapter sends the prompt alone and keeps the markdown-fence stripping that the Ollama path can drop. OpenAI-compatible endpoints vary in whether they honour `response_format`, so that adapter must degrade gracefully to prompt-only on a 400.

The consequence: **the Python validation layer stops being defence in depth and becomes load-bearing.** It is the only correctness guarantee that holds across all three adapters, and it must run identically regardless of which one produced the result.

### Fallback: ask, never silent

When the active provider is unreachable, `_scan()` raises 503 with a machine-readable body:

```json
{"detail": "Local Ollama is unreachable.",
 "provider_unreachable": true,
 "alternatives": [{"id": "anthropic", "label": "Anthropic"}]}
```

The frontend offers a single confirmation — *"Local Ollama is unreachable. Retry with Anthropic?"* — and on confirmation reposts with an explicit `provider` field. That override applies to the one request and does not change the active provider.

**The override must be a provider `id`, never a URL.** Accepting a client-supplied `base_url` would turn an authenticated OCR endpoint into an SSRF primitive against the Docker network. The id is looked up in the stored config and anything unrecognised is rejected. The OCR router is already admin-only (`ocr.py:10`), which limits but does not eliminate the concern.

### Preload is Ollama-only

The `/ocr/preload` endpoint described below is meaningful only for the Ollama adapter, which is the only one with a cold-load problem. For other provider types it returns 204 and does nothing.

### Accuracy is per-model, not per-app

Every number in "Measured accuracy" is for `qwen3.5:4b` on the Ollama adapter. Any other provider or model is unmeasured, and the prompts were tuned against one model's failure modes. This argues for keeping a **Test** button that performs a real scan of a small bundled sample image and shows the extracted fields, rather than a bare connectivity ping — a provider that connects but reads badly is the failure worth catching.

---

## Transport decision: native `/api/chat`, not the OpenAI SDK

The obvious path is to swap the `anthropic` SDK for `openai` and point it at `http://10.10.10.10:11434/v1`. That is the wrong call here, because the two things this integration needs most are not exposed on the OpenAI-compatible surface:

| Need | Native `/api/chat` | OpenAI-compat `/v1` |
|------|--------------------|---------------------|
| Disable thinking (`"think": false`) | Yes | **Accepted and silently ignored** — see below |
| Hold model resident (`"keep_alive"`) | Yes | No |
| Schema-enforced JSON (`"format"`) | Yes | Partially, different shape |

Consequences of going native:

- **No new dependency.** A plain `httpx` POST replaces the `anthropic` SDK. `openai` never gets added.
- **`"format": "json"`** (or a full JSON schema) makes the model emit valid JSON directly, which removes the markdown-fence stripping currently at `backend/app/routes/ocr.py:72-73`.
- **Images** go in the message as a `images: [b64]` array — simpler than either the Anthropic `source` block or the OpenAI `image_url` data URL.

### Thinking: measured, not assumed

Tested against the live server on 2026-09-30, warm model, trivial prompt:

| Request | `total_duration` | `eval_count` |
|---------|------------------|--------------|
| `/api/chat` with `"think": false` | **382 ms** | 12 tokens |
| `/api/chat` with `"think": true` | **15859 ms** | 724 tokens |

`think: false` works on the native endpoint: the response `message` object contains only `role` and `content`, no `thinking` key, and `content` is clean JSON. With `think: true` a `thinking` field appears carrying ~3.3 KB of reasoning.

**On the OpenAI-compatible `/v1` path, `think: false` is accepted with HTTP 200 and then ignored.** Reasoning is still generated and comes back in `choices[0].message.reasoning`.

Two things follow:

1. **This is a latency problem, not a correctness problem.** On both endpoints, reasoning is segregated into its own field and `content` stays parseable — `json.loads()` would not have raised. An earlier draft of this document claimed thinking tokens would break parsing at `ocr.py:74`. That was wrong.
2. **The latency cost is the whole argument.** ~15.5 s of wasted generation per scan, warm, on a prompt far shorter than the real OCR prompts. For a setup deliberately built around a small model to keep response time down, silently paying that on every scan defeats the point. That is the reason to go native, and it is sufficient on its own.

---

## Model residency and preloading

The notes this document replaces treated OCR as a pure SDK swap and never addressed model residency. It matters more than the payload format does.

`qwen3.5:4b` is 3.4 GB and unloads 10 minutes after its last use. A user who opens the fuel-up page cold pays the load time inside their first scan request.

### Preload endpoint

Ollama loads a model without generating anything when `POST /api/generate` is sent **with no `prompt` field**:

```json
{"model": "qwen3.5:4b", "keep_alive": "10m"}
```

This is preferable to sending a throwaway prompt, which would pay generation and vision prefill cost for output nobody reads.

Plan:

- Add `POST /ocr/preload` to `backend/app/routes/ocr.py`.
- Declare it `async def` and use an async `httpx` client. A sync handler would pin a FastAPI threadpool worker for the entire load duration.
- Return 202 on success. Swallow every failure silently — a failed warm just means the next real scan is cold, which is not a user-visible error.
- Note that `ocr.py:10` applies `require_admin` to the whole router, so the preload endpoint inherits admin-only access, consistent with the scan endpoints.

### Frontend triggers

Two triggers, both fire-and-forget (`.catch(() => {})`, no spinner, no toast, never awaited by render):

1. **Page mount** of the fuel-up page — `useEffect(..., [])`.
2. **File-picker `onChange`** — the instant a photo is selected, 2-5 seconds before the scan fires.

The second trigger is the more valuable one. Page mount alone leaves a gap: sit on the page for 11 minutes without scanning and the model has already unloaded. The second call is a cheap no-op when the model is already resident.

Same treatment applies to the expense and VIN scan entry points (`frontend/src/pages/VehicleDetailPage.tsx`, `frontend/src/pages/VehiclesPage.tsx`).

### Timeout chain

`frontend/nginx.conf:15-16` proxies `/api` to `http://api:8000` with no `proxy_read_timeout`, so the nginx default of 60s is the binding limit (axios sets no timeout of its own). Preloading makes an over-60s scan unlikely, but set `proxy_read_timeout 120s;` in that location block as a backstop for the first scan after an idle period.

---

## Measured accuracy

Everything below was measured against the live server on 2026-09-30 using four real pump photos, ten runs per photo per configuration. Ground truth was confirmed by the user; an earlier draft of this document scored results against a misreading of the Marathon photo and reached the opposite conclusion on several points.

### The photo set

| Photo | Truth | Character |
|-------|-------|-----------|
| Speedway | $65.00 / 13.405 gal | Clean backlit LCD, straight on |
| Costco | $46.03 / 12.545 gal | Clean, slight angle |
| Clear $20 | $20.00 / 5.000 gal | Close, clear, round numbers |
| Marathon | $69.00 / 20.542 gal | Heavy glare, oblique angle, ghosted seven-segment digits |

### Configuration sweep, `qwen3.5:4b`, `think: false`

| Configuration | Both fields correct |
|---------------|---------------------|
| Original prompt (arithmetic reconciliation), `format: "json"` | 0/5 on Marathon; not run on full set |
| Transcribe-only prompt, `format: "json"` | 29/40 |
| \+ explicit decimal-place counts | 32/40 |
| \+ regex string schema | **34/40** |

Two failure modes were eliminated outright by those last two changes:

- **Decimal drop** — `4603` for 46.03, `12545` for 12.545, `20542` for 20.542. Right digits, 100× magnitude error, silently plausible in a database. Zero occurrences across 80 runs once the prompt states the decimal-place counts.
- **Type instability** — 9 of 40 baseline runs returned strings where numbers were expected, which would have hit the Pydantic layer. Zero once a schema is enforced.

### Model comparison, final configuration

Same prompt, same schema, same session, ten runs per photo:

| Photo | `qwen3.5:4b` | `qwen3.5:9b` |
|-------|--------------|--------------|
| Speedway | 10/10 | 10/10 |
| Costco | 10/10 | 10/10 |
| Clear $20 | 10/10 | 10/10 |
| Marathon (glare) | 4/10 | 0/10 |
| **Total** | **34/40** | **30/40** |
| Warm median latency | 1437 ms | 1909 ms |
| Cold load | 689 ms | 4726 ms |

**On displays a person can actually read, the two models are identical at 30/30.** The entire difference is the glare photo, where 9b read `64.00` nine times out of ten and `690.00` once.

The right reading of that is not "4b is better at vision". 9b is more decisive and converges hard on a single interpretation; 4b is noisier, and on a genuinely ambiguous digit that noise lands on the correct answer some of the time. Neither model can read that display. The decision should not be over-fitted to one bad photo — but equally, there is no evidence anywhere in this data that a larger model buys accuracy on pump displays, and 9b costs 3× the cold load that motivated choosing 4b in the first place.

### Receipts and the expense route

Three further images: a Marathon fuel receipt (thermal print), a DTW parking receipt, and a Hertz booking confirmation screenshot. Ten runs each.

**Amount extraction is the strong point.** 30/30 across all three receipts, every configuration tested. Printed text is a genuinely easier problem than seven-segment digits, as expected.

**Dates are the weak point**, and the failure is silent. The Hertz screenshot prints `Sun, Dec 7` and `Mon, Dec 8` with no year anywhere. The original prompt invented one on all ten runs: `2024-12-07` ×5, `2024-12-08` ×3, `2023-12-08`, `2015-12-07`. Those weekdays pin the year exactly — Dec 7 falls on a Sunday only in 2025 — so every answer contradicted a weekday printed in the image the model was looking at. Nothing downstream catches a plausible-but-wrong year.

The rewritten prompt takes that to **9/10 correctly declined**.

| | original prompt | final prompt |
|---|---|---|
| Hertz date (no year printed, must omit) | 0/10 declined | **9/10 declined** |
| Hertz amount | 10/10 | 10/10 |
| Hertz category | `other` 10/10 | `other` 10/10 |
| DTW amount | 10/10 | 10/10 |
| DTW category | `other` 10/10 | `other` 10/10 |
| DTW date | 8/10 plausible, 1 fabricated | 6/10 transaction date, 4/10 period end, **0 wrong** |
| Fuel receipt amount | — | **28/30** |
| Fuel receipt date | 10/10 | **30/30** |
| Fuel receipt category | — | `fuel` 10/10 |

Median latency 1.3-2.0 s per scan.

Still soft: the DTW receipt prints a transaction timestamp and a separate service period, and the model picks the period end 4 times in 10 despite being told to prefer the transaction date. This is the only field where thinking measurably helps (5/5), and it is also precisely the kind of error a user spots and corrects in one tap. Left as-is.

### Model comparison, round two: receipts

| | 4b | 9b |
|---|---|---|
| Hertz amount | **10/10** | 7/10, dropped 3× |
| Hertz date declined | 9/10 | 10/10 |
| DTW category | **`other` 10/10** | `other` 7/10, omitted 3× |
| Fuel receipt category | **`fuel` 10/10** | omitted 7/10 |
| Fuel receipt date | 8/10, **0 wrong** | 7/10, `2016-12-16` twice |

9b drops fields 4b extracts reliably and invents years where 4b declines. Latency was also considered — receipts are captured indoors, so a slower model would have been acceptable there in a way it is not at the pump — but there is no accuracy to buy.

### Thinking: measured twice

Re-tested with `think: true` on both models, five runs per configuration, `num_predict` raised to 4096.

| | no-think median | think median |
|---|---|---|
| 4b, glare pump photo | 1.4 s | **68 s** |
| 4b, DTW receipt | 2.1 s | 37 s |
| 9b, DTW receipt | 2.9 s | **163 s** |
| 9b, fuel receipt | 2.2 s | 47 s |

**Perception does not improve.** The glare digit went 4/10 → 3/5 on 4b and 0/10 → 1/5 on 9b, both inside noise at n=5. No amount of reasoning recovers ambiguous pixels.

**Decisions do improve.** On the DTW receipt, which prints both a transaction timestamp and a service period, thinking picked the transaction date **5/5** against 6/10 without. That is the one field in this entire body of testing that is a genuine judgement rather than a transcription.

The first round of thinking tests appeared to show dates getting *worse*. That was an artifact of the one-clause year rule described above: the thinking model reasoned its way to correctly applying a badly written instruction and abstained, while the non-thinking model ignored the instruction and returned the right answer. Re-tested against the four-clause rule, thinking returns `2022-12-16` on 4 of 4 parsed runs.

**Parse failures are the blocker.** Even at `num_predict: 4096`: 3 of 5 on 9b/DTW, 1 of 5 on 4b/DTW, 1 of 5 on 4b/fuel. Non-thinking has not failed to parse once in roughly 300 calls. A 20% hard-failure rate is worse than a date being off by one day.

**Decision: `think: false` on every route.** The expense route was the plausible exception — receipts are captured in the car rather than in the rain, so 15 s would have been tolerable where 68 s at a pump is not. It was rejected on the parse-failure rate, not on latency. If that is ever revisited, the open question is whether a much larger budget or a retry-on-parse-failure path removes it; the accuracy gain is real but narrow, and it lands on exactly the field the user confirmation step already catches.

### Document-expiry route

Tested with an insurance certificate (the route's prompt covers registration and insurance cards; its category enum includes both). Ten runs, 4b, `think: false`. Test values are not reproduced here — the sample document carries names, a policy number and a VIN.

| Field | Result |
|-------|--------|
| `expires_on` | **10/10** |
| `category` | **10/10** `insurance` |
| `amount` | **10/10 correctly omitted** |

This is the best-performing route tested, and it was predicted to be the worst. Two things went right that had gone wrong everywhere else:

- The card prints an Effective Date *before* the Expiration Date. The prompt asks for expiry and got it every time. Labelled fields are simply easier than positional ones.
- No premium is printed on the card. The prompt asks for a fee amount and the model declined all ten times — the "omit rather than guess" behaviour that never once fired on pump displays.

Dates being the hardest field on receipts did not carry over. A clearly labelled `Expiration Date 08-25-2026` is an easy read; the difficulty on receipts was never the date itself but deciding *which* date and what to do about a missing year.

**One fix needed.** `description` returned 10 distinct strings, the longest 110 characters and **including the policy number**. That writes a policy number into a description column. Apply the same treatment the expense prompt received: cap at 6 words, and add an explicit instruction not to include policy, account or identification numbers.

### VIN route

Same insurance card, which prints a VIN. Fifteen runs per configuration.

| | exact | flagged wrong | silently wrong |
|---|---|---|---|
| Current prompt, `format: "json"` | 6/15 (40%) | 9/15 | **0** |
| Tuned prompt + regex schema | **10/15 (67%)** | 4/15 | **1/15 (7%)** |

The schema is `{"vin": {"type": "string", "pattern": "^[A-HJ-NPR-Z0-9]{17}$"}}`, and the tuned prompt adds an explicit instruction to count characters and stop at seventeen, plus `6 vs G` to the misread list.

**The tradeoff is real and worth understanding.** Forcing exactly 17 valid characters converts the most *detectable* failure — a 16-character read — into a right-length, wrong-content one. Roughly one in eleven of those passes the check digit by chance, returning `check_digit_ok: true` with no warning. Accuracy rises, and a new class of silent error appears with it.

**Best-of-3 agreement was tested and rejected.** Requiring three reads to agree exactly accepted only 1 of 12 trials, at 5.2 s per scan. The correct VIN appeared somewhere in 11 of 12, but the near-misses vary too much for unanimity to be workable. Note that voting is *statistically* valid here, unlike on pump displays — VIN misreads are diverse (five distinct wrong strings in fifteen reads) rather than systematic — it is simply not worth the machinery.

**Recommendation: take the tuned prompt and schema, accept the 7%.** This route already has defence in depth that none of the others do:

1. `ocr.py:143` rejects anything failing the 17-character regex with a 422.
2. `ocr.py:147` returns `check_digit_ok`, and `VehiclesPage.tsx:51-53` raises a visible warning when it is false, while still populating the field.
3. `VehiclesPage.tsx:108` runs an NHTSA decode that fills in make, model and year. **A wrong VIN that passes the check digit decodes to a different vehicle**, which is immediately obvious to someone photographing their own car.

Three independent layers, and the VIN lands in an editable field the user confirms. This route already implements the pattern recommended for the other three — it should be the template, not a gap.

### Upload resolution: more pixels bought nothing

Measured from true camera originals (24 MP Costco pump, 12 MP Marathon glare pump), ten runs per
setting, resized exactly as `resizeImageForUpload` does:

| setting | both fields correct | payload, 2 photos | inference |
|---------|--------------------|-------------------|-----------|
| 640 / 0.65 | **19/20** | **76 KB** | ~840 ms |
| 640 / 0.80 | 17/20 | 106 KB | ~895 ms |
| 1024 / 0.80 | 14/20 | 243 KB | ~1140 ms |
| 1600 / 0.80 (previous setting) | **19/20** | 540 KB | ~1630 ms |
| 2048 / 0.80 | 19/20 | 837 KB | ~1960 ms |

640 px matches 1600 px on accuracy at a seventh of the payload and half the inference time. The
fuel route now uses 640/0.65.

Read this as "no evidence more pixels help", not "fewer pixels are better". The glare photo scored
10, 7, **4**, 9, 9 across those five settings — if resolution mattered monotonically, 1024 would
not be the worst of them. Noise dominates at n=10 on a photo the model reads as a coin flip. What
the data does support is that the extra 460 KB per scan was not earning anything.

**Not generalised to the other routes, deliberately.** Both test photos are pump displays with
large seven-segment digits. A parking or parts receipt is dense small print where glyphs occupy far
fewer pixels, and a VIN is 17 small characters in a corner of the frame at 67% exact reads already.
Those keep their existing resolutions until measured with originals of their own.

**Stored documents are unaffected.** `uploadDocument` applies its own resize for the archived copy;
the OCR request is resized separately from the same source file.

### What remains broken

**Digit ambiguity under glare.** `64.00` vs `69.00` on the Marathon photo. This passes every arithmetic and range check that can be written — `64.00 / 20.542 = $3.11/gal` is a perfectly ordinary fuel price. No model setting, prompt change, or validation rule catches it. The reviewing human is the only control. This is the evidence behind the confirmation-step requirement below.

---

## Prompt and schema

Three prompts are specified here. All were measured; the originals they replace were not.

### Fuel route — replaces `_FUEL_PROMPT` (`ocr.py:12-25`)

The current prompt tells the model to cross-check its reading with arithmetic and correct whichever value reconciles. **Remove that instruction.** It did not catch errors in testing; it manufactured internally-consistent wrong answers and attached a confidence signal to them. One run returned $140.00 at $6.83/gal — outside the prompt's own stated sanity range, returned anyway, self-check passed.

The route accepts both pump displays and printed fuel receipts, so the prompt must handle both. A display-only version was tuned first and scored 34/40 on displays, but discarded the price-per-gallon, date and location that a receipt prints. The merged version below matches it on displays and captures the extra fields on receipts:

```
This photo shows either a gas pump display or a printed fuel receipt. Transcribe ONLY
values physically shown in the image. Do not compute, derive, infer, or correct any
value. Do not fill in a field that is not printed. Copy every digit shown, including
all decimal places. Decimal-place rules, which override what you think you see if a
decimal point is faint: the total cost always has exactly 2 digits after the decimal
point; the gallons value always has exactly 3 digits after the decimal point; the
price per gallon always has exactly 3 digits after the decimal point. On a receipt the
total may be labelled FUEL SALE, TOTAL or SALE, the gallons may be labelled GALLONS or
GAL, and the price per gallon may be labelled PRICE/G or PPG. Return ONLY valid JSON
with these keys, omitting any key whose value is not printed in the image:
{"cost": total dollar amount, "gallons": gallons, "price_per_gallon": price per gallon,
"date": transaction date as YYYY-MM-DD, "location": station brand name}
```

The decimal-place sentences are load-bearing — they are what eliminated the 100× magnitude errors. Keep them verbatim.

Schema (`format` on the request, not the bare string `"json"`):

```json
{
  "type": "object",
  "properties": {
    "cost":             {"type": "string", "pattern": "^[0-9]{1,3}\\.[0-9]{2}$"},
    "gallons":          {"type": "string", "pattern": "^[0-9]{1,2}\\.[0-9]{3}$"},
    "price_per_gallon": {"type": "string", "pattern": "^[0-9]\\.[0-9]{3}$"},
    "date":             {"type": "string"},
    "location":         {"type": "string"}
  }
}
```

Note that `date` is deliberately **not** pattern-constrained. See "Do not regex-constrain dates".

### Expense route — replaces `_EXPENSE_PROMPT` (`ocr.py:27-34`)

The original prompt's failure was dates: shown a booking confirmation printing `Sun, Dec 7` with no year, it invented one on all ten runs (`2024`, `2023`, `2015`). A fabricated year silently files an expense in the wrong year and no range check catches it. The replacement adds an explicit omission rule, moves the category list into both the prompt and the schema, and caps description length in prose:

```
Extract expense details from this receipt or purchase confirmation image. Transcribe
ONLY what is printed. Do not compute, infer, or guess any value.
amount: the final total charged. It always has exactly 2 digits after the decimal
point. If several totals are printed, take the one labelled TOTAL, Total or Amount
Due. Ignore subtotals, taxes, processing fees and per-item prices.
date: the date the purchase was made, formatted YYYY-MM-DD. Apply these rules in order:
  1. If the printed date has a four-digit year, use that year.
  2. If the printed date has a TWO-digit year, such as 12/16/22 or 09/12/26, that is
     still a printed year. Expand it into the 2000s: 22 means 2022, 26 means 2026. Do
     not omit the date.
  3. If NO year is printed at all, for example a date showing only a weekday, month and
     day such as 'Sun, Dec 7', you MUST omit the date field entirely. Never infer a
     year. Never assume the current year.
  4. If several dates are printed, prefer the transaction or payment date over a
     service period.
description: at most 6 words naming the merchant and what was bought. No dates, no
amounts.
category: exactly one of these five values, chosen by what the purchase was for:
  fuel - gasoline, diesel, or any fuel purchase
  repair - parts, maintenance, service, labour, tyres, oil changes
  insurance - an insurance premium or policy payment
  registration - vehicle registration, title, plates, inspection fees
  other - anything else, including parking, tolls, car washes, rentals
Return ONLY valid JSON. Omit any field whose value is not printed in the image.
```

```json
{
  "type": "object",
  "properties": {
    "amount":      {"type": "string", "pattern": "^[0-9]{1,5}\\.[0-9]{2}$"},
    "date":        {"type": "string"},
    "description": {"type": "string"},
    "category":    {"type": "string",
                    "enum": ["insurance", "registration", "repair", "fuel", "other"]}
  }
}
```

**The year rule must distinguish "no year" from "two-digit year".** An earlier version stated only: *if the image does not print a four-digit year, omit the date entirely.* Receipts overwhelmingly print two-digit years — `12/16/22`, `09/12/26` — so that rule, read literally, forbids almost every real date. Measured effect of splitting it into the four clauses above:

| | one-clause rule | four-clause rule |
|---|---|---|
| Fuel receipt date (`12/16/22`) | 8/10 | **30/30** |
| DTW, correct transaction date (`09/12/26`) | 1/10 | **6/10** |
| DTW, `0000-` placeholder years | 3/10 | **0/10** |
| Hertz, correctly declined (no year at all) | 9/10 | 9/10 |

The `0000-09-12` outputs were the model signalling "I can see a year but you told me it doesn't count." They disappeared the moment two-digit years were legitimised.

**The enum must appear in both places.** An intermediate version moved it into the schema only, on the assumption that the constraint was what mattered. Category accuracy collapsed — Hertz went from `other` 10/10 to `repair` 8/10, DTW from `other` 10/10 to `repair` 5/10. The schema constrains which strings can be emitted but conveys no meaning, so the model was choosing blind from options it could no longer read. Schema for enforcement, prose for semantics, both required.

### VIN route — replaces `_VIN_PROMPT` (`ocr.py:110-117`)

```
This photo shows a vehicle identification number (VIN), on a door-jamb sticker, a
windshield plate, a registration card, or an insurance card. A VIN is EXACTLY 17
characters of digits and capital letters. It never contains the letters I, O or Q.
Find the value labelled VIN and transcribe it character by character, left to right.
Count the characters as you go and stop at exactly 17. Do not skip a character. Do not
add one. Common misreads: 0 vs O (a VIN never contains O), 1 vs I (never I), 5 vs S,
8 vs B, 2 vs Z, 6 vs G. Return ONLY valid JSON: {"vin": "<the 17 characters>"}, or {}
if you cannot read all 17 clearly.
```

```json
{"type": "object",
 "properties": {"vin": {"type": "string", "pattern": "^[A-HJ-NPR-Z0-9]{17}$"}}}
```

40% → 67% exact. The pattern's cost is described under "VIN route" in Measured accuracy: it trades detectable wrong-length reads for undetectable wrong-content ones. Accepted here only because the NHTSA decode provides a second oracle.

### Document-expiry route — replaces `_DOC_EXPIRY_PROMPT` (`ocr.py:93-102`)

The original is accurate on every field but asks for "the insurer name and policy number" in `description`, and complies — one run returned 110 characters including the full policy number, bound for a free-text column. The replacement also carries the two-digit-year clause proven on receipts.

```
This is a photo or scan of a vehicle document such as a registration card or an
insurance card. Transcribe ONLY what is printed. Do not compute, infer, or guess any
value.
expires_on: the expiration or renewal date, formatted YYYY-MM-DD. Look for labels such
as 'Expiration Date', 'Expires', 'Valid Through', 'Renewal Date' or 'Policy Period
End'. If the document also prints an effective or issue date, do NOT use it. Year
rules: a four-digit year is used as printed; a two-digit year such as 08-25-26 is
expanded into the 2000s; if no year is printed at all, omit this field.
description: at most 6 words naming the insurer or the document type, for example
'Auto-Owners no-fault insurance' or 'Michigan vehicle registration'. NEVER include a
policy number, account number, VIN, licence plate, phone number or any other
identification number. NEVER include a person's name.
category: exactly one of these three values:
  insurance - an insurance certificate, card or policy document
  registration - a vehicle registration, title or licence document
  other - anything else
amount: the fee or premium dollar amount actually charged for THIS document. Most
insurance and registration cards do not print one. Ignore any dollar amount that
appears in legal text, penalty clauses, fine ranges or coverage limits — those are not
fees. If no fee or premium is printed, omit this field entirely. Never estimate it.
Return ONLY valid JSON. Omit any field whose value is not printed in the image.
```

```json
{
  "type": "object",
  "properties": {
    "expires_on":  {"type": "string"},
    "description": {"type": "string"},
    "category":    {"type": "string",
                    "enum": ["insurance", "registration", "other"]},
    "amount":      {"type": "string"}
  }
}
```

Measured: `expires_on` 12/12, `category` 12/12, description reduced from 10 distinct strings (longest 110 chars, containing a policy number) to a single 30-character string with **0/12 leaks**.

Note that `amount` is a bare string with no pattern, deliberately. See the next section.

### A regex pattern removes the ability to decline

This has now caused a fabrication three separate times, and it is the single most important thing to understand about these schemas:

| Field | Pattern applied | Result |
|-------|-----------------|--------|
| Fuel `cost` | `^[0-9]{1,3}\.[0-9]{2}$` | Unreadable display fabricated `195.00`, `50.00` instead of returning nothing |
| Expense `date` | `^[0-9]{4}-[0-9]{2}-[0-9]{2}$` | 0/10 valid; emitted `0912-20-26`, `0982-12-26` |
| Doc-expiry `amount` | `^[0-9]{1,5}\.[0-9]{2}$` | Lifted `200.00` out of the card's *penalty clause* — "fined not less than $200.00" |

A constrained field cannot be empty, so a model with nothing to report invents something shaped correctly. The rule that follows:

- **Constrain a field only when it is reliably present and purely transcribed.** Fuel cost and gallons on a pump display qualify: the numbers are always there, and copying them is not a judgement.
- **Leave it unconstrained when it is often absent, or requires transformation.** Dates, and any amount that may not be printed.
- **Filter the resulting junk in Python.** Unconstrained fields return their own garbage — the literal string `"Omit"`, an empty string, and in one case the entire JSON object nested inside the `amount` field. All trivially rejected by a shape check in code, where a fabricated-but-plausible `200.00` is not rejectable by anything.

### Do not regex-constrain dates

Pattern-constraining `date` to `^[0-9]{4}-[0-9]{2}-[0-9]{2}$` destroys it. Measured on the DTW receipt: **0/10 valid**, returning `0912-20-26`, `0913-20-09`, `0982-12-26` — the model jamming MM/DD/YY digits into YYYY-MM-DD slots. The same prompt with `date` unconstrained scored 5/10 valid, and the fuel receipt went from 10/10 to 8/10 under the constraint.

This is the opposite of the pump-display result and the distinction matters: transcribing `20.542` is *copying*, so pinning the output shape helps. Converting `12/16/22` to `2022-12-16` is *reordering*, and pinning the shape prevents the model from working in the source format. Constrain what is copied. Never constrain what is transformed.

### Description length

`maxLength` in the schema is the wrong tool — it truncates mid-word, producing `...Wayne County Airpor`. Instruct brevity in the prompt instead. With "at most 6 words" the longest observed description was 29 characters.

---

## Validation belongs in code, not the prompt

Both original prompts state sanity rules and ask the model to enforce them. Neither does. Move all of it to Python, applied before any OCR result reaches the user.

### Fuel route

| Check | Rule | Catches |
|-------|------|---------|
| Cost range | `5.00 <= cost <= 250.00` | Magnitude errors, fabrications |
| Gallons range | `1.0 <= gallons <= 45.0` | Decimal drop (`20542`), field swaps |
| Derived price | `2.00 <= cost / gallons <= 7.00` | Everything the first two miss |
| Price consistency | If `price_per_gallon` is present, require `abs(ppg - cost/gallons) < 0.02`, else **drop the ppg field** and keep the rest | A fabricated `6.500` on a display showing no price (observed 1/10) |

Against observed failures: `4603 / 12.545 = $367/gal` rejected, `20.0 / 20.0 = $1.00/gal` rejected (field swap), `195.00 / 5.000 = $39/gal` rejected.

**Not caught:** the observed `140.00 / 20.5` fabrication divides out to `$6.83/gal`, which is inside the $2-7 range. An earlier draft claimed this was rejected; it is not, and the unit test `test_fuel_cannot_catch_a_plausible_fabrication` pins that. Narrowing the range to catch it would reject real fill-ups at genuine high prices. This belongs to the same class as the glare misread — only user confirmation catches it.

### Expense route

| Check | Rule | Catches |
|-------|------|---------|
| Empty string | Treat `""` as absent | 7/10 runs return `date: ""` rather than omitting the key |
| Placeholder year | Reject any date with year < 1900 | `0000-09-12`, observed 3/10 on a two-digit-year receipt |
| Implausible year | Reject year > current year + 1 | Fabricated years |
| Missing category | Default to `other` when absent | Category omitted 2/10; `ExpenseCreate.category` is required |
| Amount | `> 0` | — |

A failed check surfaces the raw reading to the user for correction. It does not silently discard, and it does not retry.

**Do not build retry-and-vote.** On an ambiguous input the model is repeatable, not random — 9b returned the same wrong pump value nine times in ten. Majority voting returns that wrong value with a fabricated confidence signal attached.

### Document-expiry route

| Check | Rule | Catches |
|-------|------|---------|
| Amount shape | Drop `amount` unless it matches `^[0-9]{1,5}\.[0-9]{2}$` | `"Omit"`, `""`, and a nested JSON object, all observed |
| Amount sanity | Drop `amount` if `0` | Observed `0.00` |
| Expiry plausibility | Reject a date more than ~20 years from today | Misread years |
| Description | Reject if it contains a digit run of 6+ characters | Policy or account numbers surviving the prompt |

The description check is defence in depth. The prompt takes leaks from 1-in-10 to 0-in-12, but a free-text field bound for storage should not rely on prompt compliance alone.

### VIN route

Already implemented and correct — `ocr.py:143` rejects a bad shape with 422, `ocr.py:147` returns `check_digit_ok`, and `VehiclesPage.tsx:51-53` warns while leaving the field editable. No change needed. This is the template the other three routes should follow.

### Category is unvalidated today

Separate from OCR, and worth fixing while this code is open: `ExpenseCreate.category` is a bare `str(max_length=100)` (`schemas.py:249`) and the column is `String(50)` with the permitted values living only in a comment (`models.py:198`). Nothing rejects an invalid category, and the schema's 100-character limit exceeds the column's 50. The JSON-schema enum above prevents the model from producing a bad value; a Pydantic validator should prevent anything else from doing so.

### Confirmation step is mandatory

OCR output must land in the form as an editable pre-fill the user sees and confirms before save. Never an automatic write. The glare photo defeated 4b, 9b, thinking enabled, and the human reviewing this document — and produced a value passing every programmatic check. There is no version of this feature where the reading can be trusted unseen.

---

## Files that need changes

Line references verified 2026-09-30.

### 1. `backend/requirements.txt`

**Keep `anthropic==0.40.0`** (line 18) — Anthropic is now a supported provider, not a thing being removed. Add nothing else: `httpx` covers both the Ollama native API and OpenAI-compatible endpoints, so no `openai` SDK is needed. If a pinned HTTP client is not already a direct dependency, pin one; every entry in this file carries an explicit version.

### 2. `backend/app/routes/ocr.py` — ~15 lines of 147

Smaller than it looks. The four route handlers, all five prompt constants, and the VIN check-digit logic are untouched. Only the client construction and the request/response block change:

- **`_get_client()` (`:37-45`)** — replaced by a provider lookup returning one of three adapters, per "Provider architecture". The 400 "key not configured" error becomes a 400 naming the provider only when that provider type actually needs a key.
- **`_scan()` request (`:60-71`)** — `client.messages.create(...)` becomes a POST to `/api/chat` with `think: false`, `keep_alive: "10m"`, the regex schema as `format`, and the image as `images: [b64]`.
- **Response parsing (`:71`)** — `msg.content[0].text` becomes `resp["message"]["content"]`.
- **Fence stripping (`:72-73`)** — can be deleted once the schema is in place. No fenced output was observed in ~200 schema-constrained runs. Consider keeping it as belt-and-braces for one release.
- **Prompts** — replace `_FUEL_PROMPT` (`:12-25`) and `_EXPENSE_PROMPT` (`:27-34`) per "Prompt and schema". The arithmetic reconciliation instruction must go. `_VIN_PROMPT` (`:110-117`) gains the character-count instruction and a regex schema (40% → 67%). `_DOC_EXPIRY_PROMPT` (`:93-102`) is accurate as written but must stop asking for the policy number in `description`.
- **Per-route schemas** — the fuel and expense routes need different `format` schemas, so `_scan()` must take the schema as an argument alongside the prompt.
- **New:** range validation on the parsed result, per "Validation belongs in code".
- **`max_tokens=512` (`:62`)** — becomes `options: {"num_predict": ...}`. 512 is adequate with `think: false` (the JSON payloads are small), so this is a straight translation, not a bump.
- **Model arguments** — `claude-haiku-4-5-20251001` (default at `:48`) and `claude-sonnet-5` (`:85` fuel, `:143` VIN) all become `qwen3.5:4b`. **Keep the per-route `model` parameter** — not for the 9b escape hatch, which is closed, but because per-route model choice costs nothing and the expense and VIN prompts have not been benchmarked.
- **Error handling (`:77-79`)** — the broad `except Exception` currently maps everything to a 500 "OCR processing failed". With the API key check gone, an unreachable Ollama server falls into that same generic 500. Add an explicit connectivity branch returning 503 with a message that names the real cause.
- **New:** the `POST /ocr/preload` endpoint described above.

Delete the comment at `ocr.py:84` about Sonnet's high-resolution vision — it no longer describes the code.

### 3. `backend/app/routes/settings.py` (`:229-266`)

All three endpoints stay and grow. They now manage a provider list rather than a single API key.

- `get_integrations_settings()` — returns the provider list with `api_key` replaced by a masked preview, plus the active provider id. Never returns a key in full.
- `test_integrations(provider_id)` — tests one configured provider. For Ollama, `GET {base}/api/tags` confirms reachability and that the named model is present. For the others, a minimal request. Per "Accuracy is per-model", the better version scans a small bundled sample image and returns the extracted fields so a badly-reading provider is visible, not just an unreachable one.
- `save_integrations_settings()` — writes the provider list and active selection. An empty `api_key` on an existing provider means "unchanged", so a saved key is never clobbered by a UI round-trip that masked it.
- **New:** `POST /settings/integrations/active` to switch provider without rewriting the whole list.

### 4. `backend/app/schemas.py` (`:473-479`)

Replace the two Anthropic-specific classes with provider-shaped ones:

- `OcrProviderConfig` — `id`, `type` (`Literal["ollama","anthropic","openai"]`), `label`, `base_url`, `model`, `api_key`.
- `OcrProviderResponse` — the same minus `api_key`, plus `api_key_set: bool` and `api_key_preview: Optional[str]`. Reuses the existing `...abcd` masking convention.
- `OcrSettings` / `OcrSettingsResponse` — the provider list plus `active` id.
- Validate `base_url` is required and well-formed when `type` is `ollama` or `openai`, and that `api_key` is present when `type` is `anthropic`.

### 5. `backend/app/data_config.py` (`:42-44`)

**Keep the `ANTHROPIC_API_KEY` backfill and extend it.** On a config with no `integrations.ocr` section, seed one:

- Always seed the default Ollama provider pointing at `http://10.10.10.10:11434` with `qwen3.5:4b`, and make it active.
- If `ANTHROPIC_API_KEY` is set in the environment, or a legacy `integrations.anthropic_api_key` exists in `config.json`, seed an Anthropic provider alongside it so the existing key is not lost.

This doubles as the migration path for existing installs: the old single-key shape is read once and converted, and nothing is silently dropped.

### 6. `docker-compose.yml` (`:8`)

**Keep line 8.** `ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY:-}"` remains useful as a seed for the Anthropic provider on a fresh install. It is no longer required for OCR to work, only convenient.

No network changes needed: the compose file uses a standard bridge network (`vehicle-tracker-network`), and reaching a LAN host at `10.10.10.10` needs no special configuration.

### 7. `.env.example` (`:6`)

**Keep `ANTHROPIC_API_KEY=`** (line 6), now documented as an optional seed for the Anthropic provider rather than a requirement. Add a comment noting that OCR providers are configured in Settings and that the default is a local Ollama host.

### 8. `frontend/src/pages/SettingsPage.tsx` — ~85 lines of 659

**Revised down from the previous estimate of "~200+ lines".** The actual footprint:

- `:60-62` — three `useState` declarations for key, key-set flag, key preview
- `:99-100` — loading the key state
- `:242`, `:251-257` — the test and save handlers
- `:593-655` — the Integrations tab JSX block, **63 lines**

The tab grows rather than shrinking. It becomes a provider manager:

- A list of configured providers: label, type badge, model, masked key where applicable, and a radio selecting the active one.
- Add / edit / remove, with the form varying by type — Ollama and OpenAI-compatible need a base URL, Anthropic needs a key, all need a model.
- A per-provider **Test** button showing the result of a real sample scan, not just reachability.
- The existing `...abcd` key-preview convention carries over; an untouched key field means unchanged.

This is now a net addition of UI, not the ~85-line deletion the earlier plan assumed.

### 9. `frontend/src/services/api.ts`

- `getIntegrationsSettings()` (`:424`) — keep; returns the provider list.
- `testIntegrationsSettings(providerId)` (`:429`) — keep; takes a provider id instead of a key.
- `saveIntegrationsSettings(settings)` (`:434`) — keep; submits the provider list.
- **Add** `setActiveOcrProvider(id)`, `preloadOcr()`, and a `provider` argument on the four OCR calls for the fallback retry.

### 10. `backend/app/main.py`

Inspect only. No provider-specific middleware or health check is expected. Do not add a startup preload — warming at boot wastes the residency window long before any user opens the fuel page.

### 11. `README.md`, `SETUP.md`, `DEVELOPMENT.md`

**Corrected from the previous version of this document.** These files contain **no** occurrences of "Anthropic" and **no** `ANTHROPIC_API_KEY`, so there is nothing to delete from an environment-variable table. What they actually contain is the phrase "Claude Vision API":

- `SETUP.md:175` — "OCR button (Claude Vision API integration)"
- `README.md:181-183` — three bullets, VIN / fuel pump / receipt OCR
- `DEVELOPMENT.md:217` — "Implement OCR (Claude Vision API) for VIN/fuel/receipts"

Reword those to describe configurable OCR providers, and add a short setup note: OCR ships defaulting to a local Ollama host with `qwen3.5:4b`, and Anthropic or any OpenAI-compatible endpoint can be configured in Settings instead.

### 12. Tests

`backend/tests/` has **no** coverage referencing OCR or the integrations endpoints, so nothing breaks. This is also a gap: consider adding a test that mocks the Ollama `/api/chat` response and asserts `_scan()` parses it, since there is currently no automated protection against the JSON-parsing failure mode described above.

---

## Risk

| Area | Risk | Notes |
|------|------|-------|
| Thinking left enabled | **Medium** | Verified: costs ~15.5 s of wasted generation per scan, warm. Does **not** corrupt output — reasoning is returned in a separate field and `content` stays valid JSON. Mitigated entirely by `think: false` on the native endpoint, which is confirmed working. |
| Vision payload (`images` array) | **Verified** | Tested end-to-end with four real pump photos, ~200 calls. Works, no issues. |
| Digit misread under glare | **Accepted, unmitigable** | 4/10 on the glare photo, and the wrong value passes every range check. No model or prompt fixes it. Mitigation is the mandatory user confirmation step, not code. |
| Expense route accuracy | **Low, measured** | Amount 30/30 across three receipts. Date handling rewritten and verified. Remaining softness is multi-date receipts, covered by user confirmation. |
| Fabricated dates | **Medium, mitigated** | A plausible wrong year passes every programmatic check. The prompt's omission rule takes this from 0/10 to 9/10 declined, but it is not 10/10 and the user confirmation step is the backstop. |
| VIN route accuracy | **Medium, well contained** | 67% exact with the tuned prompt, ~7% of scans return a wrong VIN that passes the check digit. Contained by three independent layers including the NHTSA decode. Measured on one card; a door-jamb sticker is a harder surface and remains untested. |
| Document-expiry route accuracy | **Low, measured** | 10/10 on expiry date, category and correct omission of a missing amount. Needs the description field capped to stop policy numbers landing in it. Measured on an insurance card; a registration card remains untested. |
| Provider override as SSRF | **Medium, mitigated by design** | The fallback retry must accept a provider **id** resolved against stored config, never a client-supplied `base_url`. Accepting a URL would make an authenticated endpoint an SSRF primitive against the Docker network. Router is already admin-only. |
| Accuracy on non-default providers | **Unmeasured by definition** | All numbers here are `qwen3.5:4b` on the Ollama adapter, and the prompts were tuned against that model's failure modes. Anthropic gets no JSON schema at all. The Python validation layer is the only guarantee spanning providers. |
| Structured output not portable | **Medium** | `format` is Ollama-only. The Anthropic adapter is prompt-only and must keep the markdown-fence stripping; the OpenAI adapter must degrade gracefully when `response_format` is refused. |
| PII in extracted text | **Medium** | The document-expiry prompt asks for "the insurer name and policy number" and duly returns policy numbers in a free-text description. Cap the field and exclude identification numbers explicitly. |
| Cold-load latency | **Medium** | 3.4 GB load inside the user's first request. Preload endpoint plus the nginx timeout bump are the mitigations. |
| 4b accuracy on seven-segment digits | **Low on readable displays** | Measured 30/30 on three clean photos. The existing prompt's arithmetic cross-check does not help and was removed — it manufactured consistent wrong answers. 9b evaluated and rejected. |
| JSON output reliability from a 4b model | **Low** | Handled by the regex schema. Zero parse failures and zero type errors across ~200 constrained runs. |
| Requirements change | Low | Remove `anthropic`, add nothing. |
| Image payload | Low | Native API takes a plain base64 array. Simpler than what is there now. |
| Settings API cleanup | Low | Keep GET and test, drop save. |
| Frontend cleanup | Low | ~85 lines, mostly deletion. |

---

## Resolved: hardcoded host

Earlier drafts debated a hardcoded IP versus an `OLLAMA_BASE_URL` environment variable. Both are superseded — the host is now one field of a provider record edited in the Settings UI, with `http://10.10.10.10:11434` as the seeded default.

The original concern that motivated the debate is also resolved. An earlier draft noted: *"if the Ollama server goes down, OCR breaks with no way to reconfigure from the UI."* That is now exactly what the provider list and the ask-before-fallback flow address.

---

## Summary

| File | Action |
|------|--------|
| `backend/requirements.txt` | **Keep** `anthropic`; add no SDK (httpx covers Ollama and OpenAI-compatible) |
| `backend/app/routes/ocr.py` | Native `/api/chat` with `think: false`, `keep_alive`, per-route schema as `format`; model `qwen3.5:4b`; rewritten `_FUEL_PROMPT` and `_EXPENSE_PROMPT`; Python validation for both routes; `_scan()` takes a schema argument; keep per-route `model` arg; add 503 branch; add `POST /ocr/preload` |
| `backend/app/schemas.py` (expense) | Add a validator constraining `ExpenseCreate.category` to the five permitted values; reconcile `max_length=100` against the `String(50)` column |
| `backend/app/routes/settings.py` | Provider CRUD: list with masked keys, per-provider test, save, set-active |
| `backend/app/schemas.py` | `OcrProviderConfig` / `OcrProviderResponse` / `OcrSettings`; add the expense category validator |
| `backend/app/data_config.py` | Seed default Ollama provider; migrate legacy `anthropic_api_key` and `ANTHROPIC_API_KEY` into the provider list |
| `docker-compose.yml` | **No change** — the env line stays as an optional seed |
| `.env.example` | Keep `ANTHROPIC_API_KEY`, document it as optional |
| `frontend/nginx.conf` | Add `proxy_read_timeout 120s;` to `location /api` |
| `frontend/src/pages/SettingsPage.tsx` | Integrations tab becomes a provider manager (add/edit/remove/activate/test) |
| `frontend/src/services/api.ts` | Provider-shaped payloads; add `setActiveOcrProvider`, `preloadOcr`, `provider` arg on OCR calls |
| Fuel / expense / VIN pages | Fire-and-forget preload on mount and on file select; OCR result as editable pre-fill requiring user confirmation, never an automatic write; handle 503 `provider_unreachable` with a retry-with-other-provider confirmation |
| `backend/app/routes/ocr.py` (providers) | Adapter per provider type; `provider` override accepted as an **id only**, never a URL |
| `README.md`, `SETUP.md`, `DEVELOPMENT.md` | Reword "Claude Vision API" references |

---

## Corrections applied to the previous version of this document

1. `docker-compose.yml` was listed as needing no change. It passes `ANTHROPIC_API_KEY` at line 8.
2. `thinking: {"enabled": false}` was specified. That is the Anthropic parameter shape; Ollama's equivalent is `think: false`, and on the OpenAI-compatible endpoint it is accepted and then ignored rather than rejected.
3. The OpenAI SDK was chosen as the transport. Native `/api/chat` is required for `think`, `keep_alive`, and `format`, and needs no new dependency.
4. `ocr.py` was estimated at "~80% rewrite". It is ~15 lines of 147.
5. `SettingsPage.tsx` was estimated at "~200+ lines removed". The Integrations block is 63 lines; total footprint ~85.
6. "Anthropic-specific reasoning token extraction" was listed as code to remove. No such code exists in `ocr.py`.
7. The doc files were said to contain `ANTHROPIC_API_KEY` and Anthropic setup instructions. They contain neither — the actual references are to "Claude Vision API".
8. Removing `IntegrationsSettingsResponse` outright would 404 a call the settings page makes on load.
9. The failure mode was described as a hard "OCR unavailable" error. In reality it falls through a broad `except Exception` into a generic 500.
10. Model residency, preloading, and the nginx 60s proxy timeout were not addressed at all.
11. Risk table typo: "Intents tab" → "Integrations tab". Risk weightings reordered — thinking tokens, not image payload format, are the real exposure.
12. An intermediate draft of this document (and the review that produced it) claimed thinking tokens would break `json.loads()` at `ocr.py:74`, and rated that the highest risk in the migration. Testing disproved it: reasoning is returned in a separate field on both endpoints and `content` stays valid JSON. The real cost is ~15.5 s of wasted generation per scan. The conclusion — use native `/api/chat` with `think: false` — is unchanged, but the reason is latency, not correctness.
13. The 9b escape hatch was listed as the remedy if 4b accuracy proved insufficient. Measured: 9b is worse overall (30/40 vs 34/40), identical on readable displays, and 3× slower to load. Hatch closed.
14. An intermediate review claimed the Marathon misread was systematic and that retry-and-vote would lock in the error. At n=10 the 4b model splits 4/6 between the two readings, so it is ambiguity rather than fixed bias. The advice against retry-and-vote still stands, but on the stronger evidence of 9b, which did return the same wrong value 9/10.
15. An intermediate review flagged the clear $20 photo as a weak spot with a field-swap failure mode, based on an 8/10 batch. A second batch on identical configuration scored 10/10. That was sampling noise, not a real weakness; the field-swap mode was observed but is rarer than reported.
16. Ground truth for the Marathon photo was initially misread as $64.00 during review. It is $69.00. Several accuracy conclusions were inverted by that error and have been rescored.
17. An intermediate tuning pass regex-constrained the expense `date` field on the assumption that what worked for pump decimals would work for dates. It scored 0/10 valid on one receipt, emitting `0912-20-26` and similar. Copying and reordering are different operations; only the former should be shape-constrained.
18. The same pass moved the category enum out of the prompt and into the schema alone. Category accuracy collapsed from 10/10 to 5/10 on one receipt. The enum belongs in both.
19. The review first predicted thinking would improve date handling and not perception, then retracted that when measurements appeared to show dates getting worse, then found the measurements were corrupted by the one-clause year rule in correction 21. With the rule fixed, the original prediction is what the evidence supports: thinking fixes multi-date *selection* (5/5 vs 6/10) and does nothing for reading ambiguous digits. `think: false` is still the decision, but on the parse-failure rate and latency, not on accuracy.
20. `maxLength` in the schema was used to cap description length. It truncates mid-word. Length belongs in the prompt.
21. The expense prompt's first year rule said to omit any date lacking a four-digit year. Receipts print two-digit years as a matter of course, so the rule forbade nearly every real date. It produced `0000-` placeholder years and suppressed correct answers, and it corrupted the first round of thinking measurements by giving the more compliant model the worse-looking score. Split into four ordered clauses; fuel receipt dates went to 30/30.
22. A fuel-receipt amount score of 8/10 was reported as a possible regression from prompt length. Re-run at n=20: 20/20. It was sampling noise. Combined figure is 28/30.
23. The document-expiry route was flagged as the highest-priority untested risk, on the reasoning that it extracts dates and dates were the weakest field measured. It turned out to be the best-performing route of the four: 10/10 on expiry date, category, and correctly omitting an amount that is not printed. The inference was wrong — the difficulty on receipts was choosing between several dates and handling a missing year, not reading a labelled one.
24. The VIN regex schema improves exact reads from 40% to 67% but introduces a silent-failure class that did not previously exist, by converting detectable wrong-length reads into undetectable wrong-content ones. Accepted on the strength of the NHTSA decode as a second oracle, not because the schema is free.
25. A tuned document-expiry prompt applied a regex pattern to `amount`. Correct omission fell from 10/10 to 9/12, and one fabrication — `200.00` — was lifted from the penalty clause printed in the card's legal text. The pattern was removed; see "A regex pattern removes the ability to decline". This was the third instance of the same mistake in this document.
26. The plan originally deleted the integrations settings UI, removed the `anthropic` dependency, dropped the `ANTHROPIC_API_KEY` backfill and the compose env line, and hardcoded the Ollama host. The scope changed on 2026-09-30 to pluggable providers configured in the UI, which reverses all five. The accuracy work is unaffected — it describes the default provider's model and still stands.
27. The "hardcoded host vs `OLLAMA_BASE_URL`" open question is closed by the provider architecture rather than decided. The risk it flagged — no way to reconfigure from the UI if the Ollama box dies — is what the provider list and ask-before-fallback now solve.
28. The validation section claimed a `140.00 / 20.5` fabrication was caught by the derived-price check. It is not: `$6.83/gal` is inside the stated $2-7 range. Caught by the unit tests during implementation. The range was left alone — tightening it would reject legitimate high-price fill-ups — and the limitation is now documented and pinned by a test.
