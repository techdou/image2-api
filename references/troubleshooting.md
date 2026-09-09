# Troubleshooting

## 401 or 403

- Confirm `IMAGE_API_KEY` is loaded.
- Confirm the relay expects `Authorization: Bearer`.
- Check whether the token is enabled for the image model or required provider channel.
- Do not paste the key into logs or screenshots.

## 404

- `IMAGE_API_BASE_URL` may be missing `/v1`.
- The relay may expose a custom full endpoint. Set `IMAGE_API_GENERATIONS_URL` or `IMAGE_API_EDITS_URL`.
- The configured model alias may not exist on that relay.

## 400 invalid parameter

- Retry with a standard size like `1024x1024`, `1536x1024`, or `1024x1536` to test whether the relay rejects large or custom dimensions. GPT Image 2/2.5 allow flexible sizes up to a 3840px edge within the documented pixel/ratio limits, but some relays cap or remap sizes — check actual output in `metadata.json`.
- For GPT Image 2.5, confirm the relay actually exposes the requested Flare/Sunburst alias before using `xhigh` or `max`.
- For transparent output, use PNG or WebP. GPT Image 2 transparency is preview; GPT Image 2.5 supports it directly.
- Remove relay-unsupported fields.
- Do not send `input_fidelity` for GPT Image 2.
- Use sequential mode instead of `n > 1`.
- For edits, verify the relay implements multipart `/images/edits`.

## All providers failed (multi-provider mode)

If you configured `IMAGE_API_PROVIDERS` and every provider was exhausted:

- The error message lists each provider's last status code and reason, e.g.
  `All 2 providers failed [fenno -> backup]: fenno(HTTP 503): ...; backup(HTTP 401): ...`.
- A 401/403 from one provider means the key/permission for that provider is
  wrong — fix the key in `.env` rather than adding more fallback providers.
- A 503/429 from every provider indicates a regional outage or quota
  exhaustion; wait or upgrade the plan on the working provider.
- If only the last provider failed with a non-fallback code (e.g. 400), the
  chain did not retry because the code is not in `IMAGE_API_FALLBACK_STATUS`.
  Either fix the request or extend the fallback status set.
- Use `python scripts/doctor.py` to confirm the chain parses correctly.

## Prompt doctor fails

Run a readable report:

```bash
python scripts/prompt_doctor.py --prompt-file prompt.txt --profile auto
```

Common fixes:

- replace `masterpiece`, `best quality`, and `8K` with concrete composition, materials, lighting, and intended-use decisions;
- quote exact copy and prohibit extra text;
- add `Preserve exactly` and `Change only` sections for edits;
- identify each reference image by index and role;
- specify columns, panels, arrow direction, or spatial placement for structured visuals;
- keep transparency instructions consistent with the API settings; use PNG/WebP when `background=transparent`.

Strict mode is intentionally conservative. Use normal warning mode when a flagged choice is deliberate.

## 429

The client retries with exponential backoff and respects `Retry-After`. Reduce concurrent calls, use sequential candidates, or check relay balance and rate limits.

## 5xx or network timeout

The client retries transient failures. Increase `IMAGE_API_TIMEOUT` for complex high-quality prompts. Verify proxy and TLS settings. Disable SSL verification only for a trusted development relay.

## Response has no image

Inspect `response_summary.json` and the error. A relay may return a text status, asynchronous job ID, or nonstandard schema. This skill expects a synchronous OpenAI-compatible image response. Add a relay-specific adapter rather than polling undocumented fields blindly.

## Returned file is HTML or corrupted

The validator rejects HTML error pages and invalid image bytes. URL-based image downloads may have expired or require relay authentication. Re-run promptly and inspect the relay response.

## Mask rejected

- The mask must contain an alpha channel.
- At least part of the mask must be transparent; transparent areas indicate the edit region.
- The first image and mask must use the same dimensions and the same file format.
- The mask must be smaller than 50 MB.
- PNG or WebP are practical choices because JPEG cannot contain the required alpha channel.
- Each source/reference image must be PNG, JPEG, or WebP and smaller than 50 MB.
- A request may contain at most 16 source/reference images.

## Edit changes identity too much

- Put the identity reference first.
- Assign each image a role.
- State preservation constraints before changes.
- Use `change only X; keep everything else unchanged`.
- Reduce the edit scope.
- Reuse one approved image as the primary canvas instead of regenerating from text.

## Text is misspelled

- Quote exact copy.
- Request verbatim rendering exactly once.
- Add a spelling aid for uncommon names.
- Use medium or high quality first; on GPT Image 2.5, test `xhigh` or `max` only if a concrete typography requirement remains unmet.
- Keep copy short and inspect the output.
- For long or legally exact text, generate the visual without text and typeset it afterward.
