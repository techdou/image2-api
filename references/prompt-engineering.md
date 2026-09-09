# Prompt engineering entry point

The prompt system is organized around current GPT Image 2.5/2 workflows and relay portability.

Read in this order:

1. `gpt-image-prompt-guide.md` — model selection, current parameters, and prompting principles.
2. `prompt-recipes.md` — task-specific patterns.
3. `prompt-brief-schema.md` — deterministic JSON-to-prompt compilation.
4. `api-compatibility.md` — relay and parameter differences.

Use these scripts:

```bash
python scripts/build_prompt.py --brief brief.json --lint --output prompt.txt
python scripts/prompt_doctor.py --prompt-file prompt.txt --profile project-hero
```

The key principle is to write a maintainable creative brief, not a legacy keyword suffix.
