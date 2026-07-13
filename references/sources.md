# Source references

Reviewed on 2026-07-13.

## OpenAI official

- GPT Image Generation Models Prompting Guide: https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide
- GPT Image 2 model reference: https://developers.openai.com/api/docs/models/gpt-image-2
- Image generation guide: https://developers.openai.com/api/docs/guides/image-generation
- Create image reference: https://developers.openai.com/api/reference/resources/images/methods/generate
- Create image edit reference: https://developers.openai.com/api/reference/resources/images/methods/edit

## Agent Skills official/open specification

- Agent Skills specification: https://agentskills.io/specification
- Agent Skills overview: https://agentskills.io/home
- Anthropic Claude Code skills: https://docs.anthropic.com/en/docs/claude-code/skills
- Anthropic skill authoring guidance: https://docs.anthropic.com/en/docs/claude-code/skills
- `skills-ref` reference implementation: https://github.com/agentskills/agentskills/tree/main/skills-ref

## Implementation interpretations

- Prompt structure is a maintainability convention, not a custom API wire format.
- The activation description is intentionally narrower than the underlying scripts to avoid taking over ordinary built-in image-generation requests.
- Model-family configuration separates provider-facing aliases from capability validation.
- The strict dimension validator follows the current GPT Image 2 prompting/API guidance and treats very large custom dimensions conservatively.
- Relay behavior remains provider-specific and requires live acceptance testing.
