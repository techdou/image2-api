# Changelog

## 1.3.0 - 2026-08-24

- Unlocked `background=transparent` for GPT Image 2: OpenAI officially supports transparent output in preview (model generates a real alpha channel; PNG/WebP only), superseding the earlier "not supported" rule.
- Removed the hard validator rejection and downgraded the prompt-lint rule from `transparent-unsupported` (error) to `transparent-background-verify` (warning).
- Added local rejection for `background=transparent` combined with JPEG output (no alpha channel possible).
- Added a per-provider transparency matrix from live probes (2026-08): `fushengyunsuan` outputs real RGBA transparency when the prompt explicitly says "transparent background" (single-variable control: with the phrase 3/3 RGBA, without 9/9 RGB; the `background=transparent` field itself is not reliably passed through); `imagepro` ignores both the field and the prompt and returns opaque images.
- Stopped sending `moderation=auto` by default (the field is only sent for an explicit `--moderation low`); omitting it is semantically identical per the OpenAI API and keeps relay requests minimal.
- Updated `api-compatibility.md`, `gpt-image-2-prompt-guide.md`, `troubleshooting.md`, and `SKILL.md` with the transparency workflow and alpha-verification requirement.

## 1.2.0 - 2026-07-13

- Reworked `SKILL.md` around the Agent Skills open specification and Anthropic-compatible progressive disclosure.
- Narrowed the frontmatter activation description to explicit API/relay workflows and added a negative boundary for ordinary built-in image generation.
- Added `compatibility` and versioned `metadata` frontmatter.
- Added Agent routing documentation and positive/negative trigger evaluation fixtures.
- Added `scripts/validate_skill.py` and a machine-readable prompt-brief schema under `assets/`.
- Added explicit model-family configuration so third-party aliases retain GPT Image 2 validation.
- Corrected mask validation: source images may be JPEG/WebP, masks are PNG under 4 MB, and only dimensions must match.
- Enforced the 16-image edit-input limit and 50 MB source-image limit.
- Sanitized signed output URLs by stripping query strings and fragments from persisted response summaries.
- Prevented `--extra-param` from overriding validated standard request fields.
- Added translation-map compilation, stricter exact-copy detection, and improved product/UI profile inference.
- Centralized the package version and updated the API client user agent.
- Expanded unit, CLI, package-compliance, alias, mask, redaction, and prompt regression tests.

## 1.1.0 - 2026-07-13

- Rebuilt prompt guidance around the official GPT Image 2 prompting guide.
- Added task profiles, structured creative-brief compilation, prompt linting, edit invariants, multi-image role checks, text guidance, and reusable recipes.
- Added prompt review artifacts and model-specific API validation.

## 1.0.0 - 2026-07-11

- Initial portable Agent Skill release with OpenAI-compatible generation/edit clients, configurable relay endpoints, retries, response parsing, validation, metadata, installer, tests, and mock smoke test.
