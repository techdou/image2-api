# Agent routing and activation boundary

## Select this skill

Select `image2-api` when the request explicitly involves one or more of the following:

- an OpenAI-compatible Images API;
- a third-party GPT Image 2 relay or provider;
- `gpt-image-2` or a relay alias such as `image-2`;
- a custom `base_url`, token, endpoint, request header, or provider parameter;
- `/v1/images/generations` or `/v1/images/edits`;
- compiling or reviewing a prompt specifically for an API call;
- API-based image editing, multiple reference images, masks, compositing, or localization;
- repeatable run directories, request metadata, retries, hashes, or response normalization;
- installation, testing, debugging, or upgrading this image API skill.

Representative positive requests:

```text
Use my OpenAI-compatible relay to generate a GitHub repository hero with gpt-image-2.
```

```text
My provider calls the model image-2. Review the prompt, set the model family to GPT Image 2, and send it to /v1/images/generations.
```

```text
Use two reference images and a PNG mask through the Images edit API. Preserve identity and change only the jacket.
```

```text
Turn this project brief into a normalized GPT Image 2 prompt, but perform only a dry run.
```

## Do not select this skill automatically

Do not select it solely for requests such as:

```text
Draw a cute cat.
```

```text
Create an image for my presentation.
```

```text
Analyze this photo.
```

```text
Explain how diffusion models work.
```

```text
Build a web gallery.
```

Those requests either belong to the host's built-in image capability or are not image API execution tasks. Select this skill later only when the user explicitly introduces an API/relay requirement.

## Resolve ambiguous requests

For a bare request such as “帮我生图”, do not infer a third-party API merely because this skill is installed. Use the host image capability unless current conversation context already established that the requested operation must run through the user's relay.

For “帮我写 GPT Image 2 prompt”, select this skill when the prompt is intended for API execution, an existing relay workflow, or this skill's prompt compiler/reviewer. For general discussion without intended execution, answer directly and avoid loading the full skill.

## Choose the operation

- `generate`: no source image is required; create a new visual from text.
- `edit`: any source image, identity reference, style reference, mask, object transplant, localization, or composition is involved.
- `prompt-only`: compile/review and stop before the network call.
- `diagnostic`: validate configuration, endpoint behavior, or package compliance.

## Load references progressively

- Prompt construction → `gpt-image-2-prompt-guide.md`
- Profile-specific templates → `prompt-recipes.md`
- JSON brief fields → `prompt-brief-schema.md`
- Relay parameters and limits → `api-compatibility.md`
- Integration/install locations → `integration.md`
- Failure recovery → `troubleshooting.md`
- Source provenance → `sources.md`

Do not load every reference file by default.
