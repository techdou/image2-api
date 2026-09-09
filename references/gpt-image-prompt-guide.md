# GPT Image prompt guide

This guide covers GPT Image 2.5, GPT Image 2, and earlier GPT Image-compatible relay workflows used by this skill. For new API workflows, GPT Image 2.5 provides two choices:

- `gpt-image-2.5-flare`: speed-first; use when latency and iteration rate matter most.
- `gpt-image-2.5-sunburst`: quality-first; use when editing precision, subject preservation, or demanding final quality matters most.

Both GPT Image 2.5 models support generation, editing, transparent backgrounds, flexible resolutions, and `low|medium|high|xhigh|max|auto` quality settings. Keep model choice and API parameters separate from prompt wording.

## 1. Prompt like a visual brief, not a tag pile

Write the prompt as an art director, product designer, illustrator, or researcher would brief a visual team:

- identify the deliverable and where it will be used;
- describe the visible scene and subject in ordinary language;
- make composition, hierarchy, relationships, and invariants explicit;
- state exact text literally when text must appear;
- constrain edits by saying what changes and what must remain unchanged.

Avoid relying on generic incantations such as `masterpiece`, `best quality`, `8K`, long comma-separated style piles, unexplained camera metadata, or a separate negative-prompt grammar. Replace them with concrete decisions about materials, framing, lighting, layout, typography, and intended use.

## 2. Recommended prompt architecture

For generation:

```text
Create [deliverable]. Intended use: [surface/use]. Intended audience: [audience].

Scene and background:
[environment, depth, supporting elements]

Main subject:
[identity, appearance, materials, scale]

Action and interaction:
[pose, gaze, motion, object relationships]

Composition and hierarchy:
[framing, placement, safe space, viewpoint, panel/column structure]

Visual treatment:
[coherent medium/style, material language]

Lighting and color:
[light direction, contrast, atmosphere, palette]

On-image text:
Render only "[exact copy]" exactly once and verbatim. [placement and typography]

Constraints:
- [must-have]
- Do not include [exclusion]
```

For editing:

```text
Edit the provided image or images.

Reference-image roles:
- Image 1: primary canvas and identity source.
- Image 2: style or material reference.

Preserve exactly:
- identity, proportions, camera angle, crop, labels, and surrounding objects.

Change only:
- [one bounded change].

Integration:
- match scale, perspective, shadows, color temperature, and occlusion.

Constraints:
- keep everything else unchanged.
```

Do not include irrelevant sections. The structure exists to make requirements reviewable and maintainable; the API still receives one prompt string.

## 3. Choose Flare or Sunburst before tuning quality

Use the workflow requirement as the first decision:

- Existing GPT Image 2 workflow already meets quality needs -> start by testing **Flare** and measure latency improvement.
- Complex workflow where GPT Image 2 falls short -> start with **Sunburst** and establish the required quality first.
- If Sunburst passes, test Flare with the same prompt, references, dimensions, format, and explicit quality level; switch only if quality remains acceptable and latency improves.

Do not assume the same `quality` label produces identical quality or latency across models. Raise quality only when it fixes a concrete unmet requirement.

## 4. Core prompting techniques

### Intended use sets the visual mode

State whether the result is a repository hero, advertisement, UI mockup, educational figure, packaging concept, scientific panel, character sheet, or editorial image. This changes hierarchy and finish more reliably than generic quality words.

### Build complex scenes from environment to focal subject

A stable order is scene/background -> subject -> action/details -> composition -> constraints. Introduce the asset purpose first, then define the visible hierarchy.

### Photorealism should be explicit

Use `photorealistic`, `real photograph`, or an equivalent direct instruction. Describe believable materials, natural imperfections, lighting, framing, and action. Treat camera/lens metadata as an appearance cue rather than a guarantee of exact physical simulation.

### Layout needs positions and relationships

Prefer instructions such as:

- `subject centered with 30% negative space on the right`;
- `six equal columns connected left to right`;
- `full body visible, feet included`;
- `logo in the top-right safe area`;
- `place the object from Image 3 on the table in Image 1`.

### People and characters need action geometry

Specify crop/full-body framing, relative scale, gaze, hand/object interaction, stance, and which limbs must remain visible. For recurring identities, approve a reference first and use it in edit/reference workflows rather than relying on prompt-only regeneration.

### Text should be literal and bounded

When text must appear:

1. quote the exact wording;
2. request verbatim rendering exactly once;
3. specify language, placement, hierarchy, and typography character;
4. forbid extra text;
5. use at least `medium` for dense or small typography, then inspect the output.

For uncommon names, include a spelling aid when useful. When deterministic typography matters more than visual ideation, finish exact text in SVG, HTML, Figma, PPT, or another deterministic layout tool.

### Edits require invariants every turn

For surgical edits, restate the preserved identity, geometry, layout, camera angle, color, labels, arrows, crop, and surrounding objects. Then say `change only X` and `keep everything else unchanged`.

Repeated edits can still drift. Inspect each output. If a region must remain pixel-identical, composite the approved edited region into the original image downstream instead of relying on prompting alone.

### Multi-image workflows need explicit roles

Refer to every input by index and function:

```text
Image 1 is the primary product photo. Image 2 supplies the ceramic glaze. Image 3 supplies the background composition. Preserve Image 1's product geometry and label; apply only Image 2's surface treatment and Image 3's layout.
```

### Iterate with narrow corrections

Change one condition at a time: warmer light, remove one object, restore a background, increase safe space, fix one label, or preserve one identity detail. Large prompt rewrites make regressions harder to diagnose.

## 5. Profile-specific guidance

### Open-source project hero

Define project category, core metaphor, visual symbol, repository name, logo relationship, and target surface. Prefer one strong focal symbol plus controlled typography that remains legible at GitHub social-card size.

### Logo and mark

Ask for an original, redrawable silhouette with limited colors, balanced negative space, and no mockup surface unless needed. When a transparent asset is required, set `background=transparent` and use PNG/WebP; verify the returned alpha channel rather than accepting a painted checkerboard.

### IP character

Define silhouette, body proportions, face language, motif, materials, and no-go features. Create and approve a primary character/reference sheet before generating new scenes or poses.

### Academic diagram and infographic

Specify audience, learning objective, panels/columns, flow direction, node hierarchy, arrows, label language, background, and exclusions. Keep labels short. For publication-grade formulas or dense notation, use image generation for composition exploration and finish exact typography in a deterministic format.

### UI mockup

Describe the interface as a real product: controls, sections, spacing, hierarchy, state, device frame, and interaction context. Avoid decorative “futuristic HUD” language unless explicitly required.

### Advertisement

Write a creative brief: brand positioning, audience, cultural context, campaign idea, scene, composition, and exact copy. Give strong taste boundaries without prescribing every pixel.

### Comic/storyboard

Define one visual beat per panel, concrete actions, camera progression, exact dialogue, and recurring character invariants. Number panels explicitly.

### Product mockup and extraction

Preserve product geometry, labels, brand marks, and proportions. For background removal, request an isolated subject and also set the API background to transparent; prohibit checkerboards, scenery, halos, or product restyling.

## 6. API settings that interact with prompt workflows

### GPT Image 2.5

- models: `gpt-image-2.5-flare`, `gpt-image-2.5-sunburst` and dated `2026-09-08` snapshots;
- quality: `low`, `medium`, `high`, `xhigh`, `max`, `auto`;
- size: `auto` or a valid custom `WIDTHxHEIGHT`;
- each edge <= 3840 px;
- both edges divisible by 16;
- long:short ratio <= 3:1;
- total pixels 655,360-8,294,400;
- outputs above 3,686,400 pixels (`2560x1440`) are experimental;
- background: `auto`, `opaque`, or `transparent`;
- transparent output requires PNG or WebP.

Use `xhigh` or `max` only when they solve an unmet quality requirement within the latency budget. A higher label is not guaranteed to improve every prompt.

### GPT Image 2

- quality: `low`, `medium`, `high`, `auto`;
- flexible size constraints match the 3840/16-pixel/3:1/pixel-budget rules above;
- transparent PNG/WebP output is available in preview;
- omit `input_fidelity`; GPT Image 2 always processes image inputs at high fidelity.

### Older GPT Image families

GPT Image 1.5/1 use the standard `1024x1024`, `1024x1536`, `1536x1024`, or `auto` sizes. They support transparent PNG/WebP output and configurable `input_fidelity`; consult current official docs before maintaining a legacy workflow because these models have published shutdown dates.

## 7. Prompt review checklist

Before the API call, verify:

- deliverable and intended use are explicit;
- focal subject and action are unambiguous;
- layout-critical elements have positions and relationships;
- visual treatment is coherent rather than a style pile;
- exact text is quoted and extra text is forbidden;
- edit invariants and change scope are stated;
- every reference image has an indexed role;
- model family, quality, size, format, and transparency settings are compatible;
- output is inspected for text accuracy, identity/product preservation, unwanted changes, crop, geometry, and real alpha transparency.

Use `scripts/prompt_doctor.py` for deterministic prompt checks and a generation/edit dry run for API-option validation.
