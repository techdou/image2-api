# image2-api

`image2-api` is an Agent Skill for generating and editing images through an OpenAI-compatible Images API or third-party GPT Image 2 relay. Version 1.2 adds a strict Agent Skills activation boundary, relay-alias model-family handling, package validation, trigger-evaluation fixtures, and several API-safety corrections.

This skill is intentionally **not** the default route for ordinary “draw an image” requests. Use it when the workflow explicitly requires an API/relay, custom endpoint, model alias, image-edit request, mask, prompt compiler/reviewer, or reproducible run metadata.

## What it provides

- Text-to-image calls through `/images/generations`
- Image editing, localization, compositing, multiple references, and masks through `/images/edits`
- Structured JSON brief → GPT Image 2 creative-brief compilation
- Prompt profiles and deterministic prompt review
- Third-party model alias support through `IMAGE_API_MODEL_FAMILY`
- Dry-run request validation before network execution
- Base64 and URL response normalization
- Retry handling and sanitized response summaries
- Image integrity, dimension, format, and SHA-256 metadata
- Sequential candidate generation and contact sheets
- Agent Skills structural validation and trigger fixtures
- Offline unit tests and a local mock relay smoke test

## Package layout

```text
image2-api/
├── SKILL.md
├── README.md
├── assets/
│   └── prompt-brief.schema.json
├── evals/
│   └── trigger-cases.json
├── examples/
│   ├── briefs/
│   └── prompts/
├── references/
├── scripts/
│   ├── image2lib/
│   ├── build_prompt.py
│   ├── prompt_doctor.py
│   ├── generate_image.py
│   ├── edit_image.py
│   ├── doctor.py
│   ├── validate_skill.py
│   └── smoke_test.py
└── tests/
```

## Install dependencies

```bash
python -m pip install -r requirements.txt
```

Python 3.10 or newer is recommended. Prompt compilation, linting, dry runs, package validation, and tests work without a live API.

## Configure a relay

Copy `.env.example` to `.env` and keep it out of source control:

```dotenv
IMAGE_API_KEY=replace_with_token
IMAGE_API_BASE_URL=https://relay.example.com/v1
IMAGE_API_MODEL=image-2
IMAGE_API_MODEL_FAMILY=gpt-image-2
```

`IMAGE_API_MODEL_FAMILY` is important when the provider renames the model. Without it, an unrecognized alias is treated as `generic`, so GPT Image 2-specific checks cannot be applied reliably.

Check configuration without spending credits:

```bash
python scripts/doctor.py
```

Send a real low-quality probe only when desired:

```bash
python scripts/doctor.py --probe
```

## Compile a normalized prompt

```bash
python scripts/build_prompt.py \
  --brief examples/briefs/open-source-project-hero.json \
  --profile project-hero \
  --lint \
  --strict \
  --output prompt.txt
```

Print the machine-readable brief schema:

```bash
python scripts/build_prompt.py --print-schema
```

The same schema is stored at `assets/prompt-brief.schema.json`.

## Review an existing prompt

```bash
python scripts/prompt_doctor.py \
  --prompt-file prompt.txt \
  --profile project-hero \
  --model image-2 \
  --model-family gpt-image-2 \
  --quality high \
  --strict
```

Prompt review is local and deterministic. It catches common omissions and contradictions; it cannot guarantee artistic quality or perfect model compliance.

## Generate images

Validate first:

```bash
python scripts/generate_image.py \
  --prompt-file prompt.txt \
  --prompt-profile project-hero \
  --model image-2 \
  --model-family gpt-image-2 \
  --size 1536x1024 \
  --quality medium \
  --dry-run \
  --json
```

Execute:

```bash
python scripts/generate_image.py \
  --prompt-file prompt.txt \
  --prompt-profile project-hero \
  --model image-2 \
  --model-family gpt-image-2 \
  --size 1536x1024 \
  --quality medium \
  --count 4 \
  --batch-mode sequential \
  --output-dir outputs/project-hero
```

Sequential mode is more portable than relying on relay support for `n > 1`.

## Edit with references or a mask

```bash
python scripts/edit_image.py \
  --image primary.jpg \
  --image identity-reference.png \
  --prompt-file edit-prompt.txt \
  --prompt-profile edit \
  --model image-2 \
  --model-family gpt-image-2 \
  --quality high \
  --output-dir outputs/revision-01
```

Masked edit:

```bash
python scripts/edit_image.py \
  --image source.jpg \
  --mask mask.png \
  --prompt-file edit-prompt.txt \
  --model-family gpt-image-2
```

The source image may be PNG, JPEG, or WebP. The mask must be a PNG smaller than 4 MB, contain an alpha channel with a transparent edit region, and match the first source image's dimensions. A request accepts at most 16 input images; each source image must be smaller than 50 MB.

## Outputs

Each run directory preserves:

```text
prompt.txt
prompt_review.json
request.json
response_summary.json
metadata.json
image_01.png
...
```

Credentials are never written to these files. Base64 payloads are omitted from summaries, and URL query strings/fragments are stripped because signed URLs may contain secrets.

## Install as an Agent Skill

Standard user-level location:

```bash
python scripts/install_skill.py --target agents --scope user
```

Claude Code user-level location:

```bash
python scripts/install_skill.py --target claude --scope user
```

Project-local location:

```bash
python scripts/install_skill.py \
  --target agents \
  --scope project \
  --project-dir /path/to/project
```

The installed directory is always named `image2-api`, matching the `name` in `SKILL.md`.

## Validate and test

```bash
python scripts/validate_skill.py
python -m unittest discover -s tests -v
python scripts/smoke_test.py
python -m compileall scripts tests
```

When the reference validator is installed, also run:

```bash
skills-ref validate .
```

Use `evals/trigger-cases.json` to test skill-selection quality in the target Agent runtime. The local validator checks the fixtures but does not emulate a proprietary router.

## Documentation map

- `references/agent-routing.md` — positive and negative activation rules
- `references/gpt-image-2-prompt-guide.md` — model-specific prompt design
- `references/prompt-recipes.md` — profile-specific patterns
- `references/prompt-brief-schema.md` — brief authoring guide
- `references/api-compatibility.md` — endpoints, model family, limits, relay differences
- `references/integration.md` — installation and Agent execution loop
- `references/troubleshooting.md` — failure diagnosis
- `references/agent-skills-compliance.md` — package-format notes
- `references/sources.md` — official sources and interpretation notes

## Known boundaries

- No live third-party relay is validated until a real key, base URL, and model alias are supplied.
- A relay may accept the OpenAI request shape while ignoring options or omitting edit/mask support.
- The client handles synchronous image responses; asynchronous provider-job polling is not implemented.
- Prompt linting and file validation cannot judge anatomy, semantics, typography accuracy, composition, or identity preservation. Inspect actual outputs with vision.
