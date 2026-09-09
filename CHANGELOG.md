# Changelog

## 1.4.0 - 2026-09-09

- Merged the GPT Image 2.5 upgrade package (shipped externally as its own "1.3.0" dated 2026-09-09, see entry below) with the same-day local maintenance work; unified to 1.4.0 to avoid clashing 1.3.x numbers.
- Preserved from local maintenance: provider chain pruned 7 -> 3 (`fushengyunsuan`, `cunai`, `imagepro`) in `.env`; capability matrices refreshed from 2026-09-09 live probes (`cunai` first verified for landscape + real RGBA transparency; `imagepro` documented to ignore both requested size and output format).
- Restored the per-provider transparency matrix and workflow section (present in local docs, dropped by the 2.5 upgrade package) and adapted its wording to the 2.5 capability model.
- The provider matrices in `api-compatibility.md` reflect the 3-provider chain on top of the 2.5-upgraded code base.
- Added `happyevering` as chain primary running `gpt-image-2.5-sunburst`; live probe 2026-09-10 verified real 1536x1024 output and true RGBA transparency — first live GPT Image 2.5 generation through this skill. Existing providers shift to fallback positions.
- Fixed a provider-chain bug in `APIConfig.from_env` shipped with the 2.5 package: in chain mode, explicit `--model`/`--model-family`/`--base-url`/`--timeout`/`--max-retries` arguments were silently discarded in favor of the primary provider's fields, so `gpt-image-2.5-*` models could never pass capability validation on chain-configured machines (only reproducible with an `IMAGE_API_PROVIDERS` `.env`; the package's own tests ran in a clean environment). Explicit arguments now take precedence, and an explicit model without an explicit family infers the family instead of inheriting the primary's.

## 1.3.0 - 2026-09-09

- Added first-class GPT Image 2.5 Flare/Sunburst support, including `2026-09-08` snapshots and a new `gpt-image-2.5` capability family.
- Added capability-based model validation instead of scattered GPT Image 2 string checks.
- Added `xhigh` and `max` quality support for GPT Image 2.5 while retaining GPT Image 2 quality limits.
- Updated transparent-background behavior: GPT Image 2.5 supports transparent PNG/WebP; GPT Image 2 is allowed with a preview warning.
- Updated flexible-size validation and added an experimental-tier warning above 3,686,400 pixels.
- Updated mask validation to current same-format, same-size, alpha-channel, and <50 MB requirements; mask MIME type is now detected dynamically.
- Added Flare-vs-Sunburst routing guidance and a generalized GPT Image prompt guide.
- Kept the default configured relay model on GPT Image 2 for backward compatibility with third-party providers.
- Fixed two pre-existing fallback environment test fixtures and expanded regression coverage for GPT Image 2.5.

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
