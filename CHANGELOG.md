# Changelog

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
