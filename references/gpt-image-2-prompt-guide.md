# GPT Image 2 prompt guide

This guide targets the API model `gpt-image-2`, which corresponds to the newer ChatGPT Images 2.0 generation family. It is not a Stable Diffusion-style tag model and does not benefit from long strings of generic quality keywords.

## 1. The central change from older prompt styles

Write the prompt as an art director or product designer would brief a visual team:

- identify the deliverable and where it will be used;
- describe the visual situation in ordinary language;
- make relationships, hierarchy, and invariants explicit;
- let the model make bounded taste decisions inside those constraints.

The model accepts minimal prompts, paragraphs, labeled sections, and JSON-like structures. For repeatable production workflows, short labeled sections are easiest to review and revise. The API still receives one prompt string; the structure is for clarity, not special syntax.

Avoid relying on:

- `masterpiece`, `best quality`, `8K`, `ultra detailed`;
- large comma-separated style piles;
- unexplained camera metadata;
- a separate negative-prompt grammar;
- repeated synonyms that do not change the design decision.

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
- identity, proportions, camera angle, crop, lighting, labels, and surrounding objects.

Change only:
- [one bounded change].

Integration:
- match scale, perspective, shadows, color temperature, and occlusion.

Constraints:
- keep everything else unchanged.
```

Do not include every section when it is irrelevant. The goal is clarity, not prompt length.

## 3. Core model-specific techniques

### Intended use sets the visual mode

State whether the result is a repository hero, advertisement, interface mockup, educational figure, packaging concept, character sheet, or editorial image. This changes the expected hierarchy and finish more reliably than generic quality words.

### Scene before subject for complex compositions

A stable order is scene/background → subject → key details → constraints. Introduce the asset purpose in the opening sentence, then build the visual from environment to focal subject.

### Photorealism must be direct

Use the word `photorealistic` or a clear real-camera phrase. Describe natural textures, believable imperfections, unposed action, and real lighting. Lens and film language helps establish framing and character, but should not be treated as exact physical simulation.

### Layout needs coordinates and relationships

Use unambiguous relationships:

- `subject centered with 30% negative space on the right`;
- `six equal columns connected left to right`;
- `full body visible, feet included`;
- `logo in the top-right safe area`;
- `Image 3's object placed on the table in Image 1`.

### People and characters need action geometry

Specify full-body or crop, relative scale, gaze, hand/object interaction, stance, and which limbs must remain visible. This reduces incorrect poses and ambiguous interactions.

### Text should be literal and bounded

For copy that must be rendered:

1. quote the exact wording;
2. ask for verbatim rendering exactly once;
3. specify language, placement, hierarchy, and font character;
4. forbid extra text;
5. choose `medium` or `high` for small or dense typography;
6. inspect the result manually.

For uncommon brand names, add a spelling aid, for example: `TechDou — T-e-c-h-D-o-u`.

When text is not necessary, explicitly request no rendered text and add final typography later in HTML, Figma, SVG, or another deterministic layout tool.

### Edits require invariants on every turn

Restate what must remain unchanged on each edit. For surgical changes, name the preserved identity, geometry, layout, camera angle, color, labels, arrows, surrounding objects, and image quality. Then say `change only X` and `keep everything else unchanged`.

### Multi-image workflows require roles

Refer to every input by index and function. Do not say only `use these references`.

Good:

```text
Image 1 is the primary product photo. Image 2 supplies the ceramic glaze. Image 3 supplies the background composition. Preserve Image 1's product geometry and label; apply only Image 2's surface treatment and Image 3's layout.
```

### Iterate with small corrections

Start with a clean base prompt. After review, make one or two concrete corrections: warmer light, remove an extra object, restore the original background, increase safe space, or fix one label. Large rewrites make regressions harder to diagnose.

## 4. Profile-specific guidance

### Open-source project hero

Define the project category, core metaphor, visual symbol, repository name, logo relationship, and destination surface. Prefer a strong central symbol plus controlled typography. Keep the visual understandable at GitHub social-card size. Generate the logo mark separately when exact reuse matters, then provide it as a reference for the hero.

### Logo and mark

Ask for a simple, original, redrawable silhouette with limited colors and no mockup surface unless explicitly needed. Generate an opaque background, then vectorize or remove the background downstream. Do not expect a raster generation to be production-ready vector artwork.

### IP character

Define silhouette, body proportions, face language, motif, materials, and no-go features. Create a primary character sheet first, approve it, then use edit mode for new scenes and poses.

### Academic diagram and infographic

Specify audience, learning objective, number of columns/panels, flow direction, node hierarchy, arrow behavior, label language, background, and exclusions. Keep labels short. For publication-quality mathematical notation or dense text, use the model for composition exploration and finish exact typography in SVG/PPT/HTML when needed.

### UI mockup

Describe the application as if it already exists. Name real controls, sections, spacing, hierarchy, state, and device frame. Avoid `concept art`, `futuristic HUD`, and decorative interface language unless that is the explicit product.

### Advertisement

Write a creative brief: brand positioning, audience, cultural context, campaign idea, scene, composition, and exact copy. Give taste boundaries instead of prescribing every pixel.

### Comic or storyboard

Define one visual beat per panel, concrete actions, camera progression, exact dialogue, and recurring character invariants. Use numbered panel descriptions.

### Product mockup

Specify product geometry, label integrity, materials, background, contact shadow, scale, and intended commerce surface. For edits, prohibit restyling when only extraction or background replacement is required.

## 5. API settings that interact with prompts

- `quality=low`: drafts, thumbnails, ideation, high-volume variants.
- `quality=medium`: general production candidates.
- `quality=high`: dense typography, detailed educational visuals, close portraits, identity-sensitive edits, and final assets.
- Standard portable sizes: `1024x1024`, `1536x1024`, and `1024x1536`.
- Common flexible sizes include `2048x1152`, `2048x2048`, and `2560x1440`, subject to relay support.
- Official GPT Image 2 does not support transparent output. Use an opaque/plain background and remove it later.
- Omit `input_fidelity`; it is fixed at high fidelity for GPT Image 2 inputs.

## 6. Prompt review checklist

Before calling the API, verify:

- The deliverable and intended use are explicit.
- The focal subject and action are unambiguous.
- Layout-critical elements have positions and relationships.
- The visual medium is coherent rather than a style pile.
- Exact text is quoted and extra text is forbidden.
- Edit invariants and change scope are stated.
- Every reference image has an indexed role.
- Unsupported transparency or legacy API parameters are absent.
- The requested quality is appropriate for text density and identity sensitivity.

Use `scripts/prompt_doctor.py` to automate the most common checks.
