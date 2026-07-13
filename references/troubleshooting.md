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

- Retry with a standard size like `1024x1024`, `1536x1024`, or `1024x1536` to test whether the relay rejects large or custom dimensions. GPT Image 2 supports up to 3840×3840 natively, but some relays cap resolution or remap sizes — check actual output in `metadata.json`.
- Remove relay-unsupported fields.
- Use `background=auto` rather than transparent for `gpt-image-2`.
- Do not send `input_fidelity` for GPT Image 2.
- Use sequential mode instead of `n > 1`.
- For edits, verify the relay implements multipart `/images/edits`.

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
- remove requests for transparent GPT Image 2 output.

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

- The mask must be PNG and contain an alpha channel.
- At least part of the mask must be transparent; transparent areas indicate the edit region.
- The first image and mask must use the same dimensions; their file formats may differ.
- The PNG mask must be smaller than 4 MB.
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
- Use medium or high quality.
- Keep copy short and inspect the output.
- For long or legally exact text, generate the visual without text and typeset it afterward.
