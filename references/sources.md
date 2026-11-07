# Source references

Reviewed on 2026-11-07.

## OpenAI official

- OpenAI API release notes: https://developers.openai.com/api/docs/changelog
- GPT Image 2.6 Flare: https://developers.openai.com/api/docs/models/gpt-image-2.6-flare
- GPT Image 2.6 Sunburst: https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst
- GPT Image prompting guide: https://developers.openai.com/api/docs/guides/image-prompting
- Image generation/editing guide: https://developers.openai.com/api/docs/guides/image-generation
- GPT Image 2.5 Flare model reference: https://developers.openai.com/api/docs/models/gpt-image-2.5-flare
- GPT Image 2.5 Sunburst model reference: https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst
- GPT Image 2 model reference: https://developers.openai.com/api/docs/models/gpt-image-2
- Images API reference: https://developers.openai.com/api/reference/resources/images

## Agent Skills official/open specification

- Agent Skills specification: https://agentskills.io/specification
- Agent Skills description optimization: https://agentskills.io/skill-creation/optimizing-descriptions
- OpenAI skill activation and metadata: https://learn.chatgpt.com/docs/build-skills
- Agent Skills overview: https://agentskills.io/home
- Anthropic Claude Code skills: https://docs.anthropic.com/en/docs/claude-code/skills
- `skills-ref` reference implementation: https://github.com/agentskills/agentskills/tree/main/skills-ref

## Implementation interpretations

- Prompt structure is a maintainability convention, not a custom API wire format.
- The activation description is intentionally narrower than the underlying scripts to avoid taking over ordinary built-in image-generation requests.
- Model-family configuration separates provider-facing aliases from capability validation.
- GPT Image 2.6 Flare suits fast iteration. Sunburst suits precise edits and detailed output. Both can return native animated GIFs through the Images API when the project has access.
- GPT Image 2.5 and GPT Image 2 flexible sizes are validated against the documented edge, multiple-of-16, aspect-ratio, and pixel-budget rules; requests above 3,686,400 pixels receive an experimental-tier warning.
- Transparent output requires PNG/WebP. GPT Image 2 transparency is flagged as preview; GPT Image 2.5 transparency is supported directly.
- Mask validation follows the current same-format, same-size, <50 MB, alpha-channel requirements.
- Relay behavior remains provider-specific and requires live acceptance testing.
