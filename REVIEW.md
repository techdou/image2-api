# Quality review — image2-api v1.2.0

## Executive assessment

Version 1.1.0 had a solid API client and useful prompt tooling, but it was not yet a high-confidence Agent Skill. Its main weakness was not image generation itself; it was activation precision. The frontmatter could match ordinary image requests, the package directory did not match the declared skill name, detailed and volatile API behavior was mixed into the entry document, and there was no trigger-evaluation or structural validation layer.

Version 1.2.0 upgrades the package into a narrower, progressively disclosed API/relay skill and fixes several execution defects found during the review.

## Review scores

| Dimension | v1.1.0 | v1.2.0 |
|---|---:|---:|
| User setup and discoverability | 7.8/10 | 9.1/10 |
| Agent activation precision | 6.2/10 | 9.2/10 |
| Agent workflow clarity | 7.4/10 | 9.1/10 |
| Agent Skills format compliance | 6.5/10 | 9.3/10 |
| API safety and relay compatibility | 7.8/10 | 9.2/10 |
| Prompt-system quality | 8.4/10 | 9.1/10 |
| Testability and maintainability | 7.6/10 | 9.3/10 |
| Overall | 7.4/10 | 9.2/10 |

These are engineering review scores, not live-generation quality scores. A real third-party relay acceptance test is still required.

## User-perspective findings and upgrades

### 1. Setup did not explain hidden model aliases

A provider alias such as `image-2` bypassed GPT Image 2-specific checks because validation relied on the literal model name. Users could unknowingly request unsupported transparency or send incompatible fields.

**Upgrade:** Added `IMAGE_API_MODEL_FAMILY` and `--model-family`. The provider-facing alias and the underlying capability family are now separate concepts. Unknown aliases in `auto` mode emit a warning.

### 2. Mask instructions and implementation were incorrect

Version 1.1 required the first source image and mask to share a file format and allowed the mask to use the 50 MB source-image limit. Official edit behavior permits JPEG/WebP source images with a PNG mask, while the mask has a smaller limit.

**Upgrade:** Source images support PNG, JPEG, and WebP under 50 MB. Masks must be PNG under 4 MB, include a transparent alpha region, and match only the first image's dimensions. Edit requests are limited to 16 source images.

### 3. Relay extension parameters could override validated fields

`--extra-param` was merged after validation and could replace core fields such as `model`, `prompt`, or `size`.

**Upgrade:** Standard request fields, images, and mask are reserved and cannot be overridden through extension parameters.

### 4. Response summaries could persist signed URL secrets

The documentation said signed URLs were sensitive, but response summaries retained query strings and fragments.

**Upgrade:** Persisted URLs now keep only scheme, host, and path. Base64 data remains omitted and secret-like fields are redacted.

### 5. Documentation was accurate in broad strokes but hard to navigate

Users had to move between a long `SKILL.md`, README, and reference files without a clear “first action” or distinction between offline prompt work, dry runs, and paid live calls.

**Upgrade:** README now provides a direct installation/configuration/compile/review/dry-run/execute path. The completion contract explicitly distinguishes prompt-only and dry-run results from live image generation.

## Agent-matching findings and upgrades

### 1. The description was too broad

The old description included general image generation, logos, diagrams, UI mockups, and prompt design. A host could select the third-party API skill for a basic request such as “draw a cat,” even when the built-in image tool was the correct route.

**Upgrade:** The description now triggers on explicit API/relay signals and includes a negative boundary for ordinary built-in generation. `references/agent-routing.md` provides positive, negative, and ambiguous examples.

### 2. The package name and directory could diverge

The archive root was `image2-api-skill`, while frontmatter declared `image2-api`. Agent Skills requires the parent directory to match `name`.

**Upgrade:** The final package root is `image2-api/`. The installer also uses that exact destination.

### 3. Progressive disclosure was incomplete

The entry document carried detailed model constraints that can change, while routing guidance was not isolated.

**Upgrade:** `SKILL.md` now contains only activation, routing, workflow, safety, and completion rules. Prompt details, API limits, troubleshooting, and integration live in one-level reference files loaded only when needed.

### 4. No selection-evaluation fixtures existed

There was no repeatable way to assess whether a revised description became too broad or too narrow.

**Upgrade:** Added 11 positive/negative/ambiguous cases in `evals/trigger-cases.json`. These are host-router fixtures, not a claim that all proprietary routers behave identically.

### 5. No package validator existed

The project had runtime tests but no structural check for frontmatter, directory naming, resource links, version consistency, schema synchronization, examples, or trigger fixtures.

**Upgrade:** Added `scripts/validate_skill.py`, compatible with offline use. The open `skills-ref validate` command remains an additional optional check when installed.

## Prompt-system findings and upgrades

- Translation fields were recognized by the schema but not emitted into compiled edit prompts. Fixed with a bounded `Text replacement map` section.
- Uppercase tokens were incorrectly treated as exact quoted copy. Fixed; exact text now requires quotation marks or an explicit verbatim field.
- Product mockups could be inferred as UI mockups due to the generic word “mockup.” Product/packaging inference now takes precedence.
- Text-request detection could confuse preserved existing labels or “do not add copy” with a request for new text. Active text instructions are now distinguished from preservation/exclusion language.
- The academic-diagram example now provides exact module labels instead of asking for unspecified labels.

## Automated verification

The final package is verified with:

```text
47 unit and CLI regression tests passed
9 example briefs compiled and passed strict prompt review
Local mock generation/edit smoke test passed
Python compileall passed
Local Agent Skill structural validator passed
Installer copy test passed
Final ZIP re-extraction test passed
```

## Remaining boundaries

- No real request was sent because no third-party token, base URL, and provider alias were supplied for acceptance testing.
- Prompt review is heuristic and cannot prove visual quality.
- File validation cannot judge typography, anatomy, semantic correctness, composition, or identity preservation.
- The client expects synchronous image responses and does not poll asynchronous provider jobs.
- Host-level trigger fixtures still need to be run in each target Agent runtime because routing implementations differ.
