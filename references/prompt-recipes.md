# GPT Image 2 prompt recipes

These are task patterns, not mandatory suffixes. Replace bracketed content and remove irrelevant sections.

## Open-source project hero with logo and repository name

```text
Create a polished 16:9 repository hero image for an open-source project. Intended use: GitHub README header and social preview.

Project concept:
[one-sentence description of what the project does and who uses it].

Main visual symbol:
[one original metaphor that communicates the core function]. Make it immediately recognizable at small size.

Composition and hierarchy:
Place the symbol on the left or center-left. Reserve a clean text-safe region for the project name. Use a clear three-level hierarchy: mark, repository name, short descriptor. Keep generous margins for social-card cropping.

Visual treatment:
[coherent design language], original and non-infringing, with a limited palette and a clean silhouette.

On-image text:
Render only "[PROJECT NAME]" exactly once and verbatim. Optional secondary line: "[SHORT DESCRIPTOR]". No other text.

Constraints:
- No unrelated logos, watermarks, UI chrome, or stock-code imagery.
- Do not combine multiple unrelated metaphors.
```

For a reusable visual system, generate and approve the logo mark separately, then use it as Image 1 in edit mode when creating the hero.

## Logo mark

```text
Create an original logo mark for [project/brand]. Intended use: favicon, repository avatar, app icon, and documentation header.

Concept:
[one simple visual metaphor].

Shape language:
A distinctive, redrawable silhouette with [rounded/geometric/organic] forms, strong figure-ground separation, and no fine details that disappear at 32 px.

Color:
No more than [2–4] dominant colors. Generate on a plain opaque background.

Constraints:
- Symbol only; no text unless a wordmark is explicitly requested.
- No mockup surface, 3D room, stationery, watermark, or unrelated emblem.
- Original design; do not imitate an existing logo.
```

## IP character primary sheet

```text
Create a primary character design sheet for [name/role]. Intended use: recurring brand IP and future reference-image edits.

Identity:
[species/body shape], [distinctive silhouette], [face language], [signature motif], [materials/clothing].

Sheet layout:
Front view, three-quarter view, side view, back view, four facial expressions, and a small scale/silhouette comparison. Keep proportions and colors identical across all views.

Visual treatment:
[one coherent medium], neutral studio background, even lighting, clear separation between views.

On-image text:
Only short labels for views and expressions, or no text.

Constraints:
- No redesign between views.
- No extra accessories, costume variants, or background scene.
```

## Photorealistic candid image

```text
Create a photorealistic candid photograph of [subject] [action] in [environment].

Framing:
[full body/waist-up/close-up], [eye-level/low-angle/top-down], with [gaze and interaction].

Reality cues:
Natural skin/material texture, believable wear and imperfections, physically plausible shadows, and an unposed moment. [High-level camera or film character].

Lighting and atmosphere:
[time of day, softness, contrast, weather, color balance].

Constraints:
- No glamorized retouching, plastic skin, staged pose, text, watermark, or unrelated objects.
```

## Academic mechanism diagram

```text
Create a clean academic mechanism diagram for [method/topic]. Intended audience: [students/researchers/reviewers].

Learning objective:
The figure must show [core relationship or process].

Structure:
[exact number] columns from left to right: [column names]. Group modules with [box style]. Use consistent arrows with clear direction. Show [required nodes/labels] and no others.

Visual hierarchy:
White background, generous spacing, short English/Chinese labels, one consistent icon system, and readable hierarchy at slide size.

Visual treatment:
Flat vector figure, thin lines, restrained low-saturation fills, no decorative 3D effects.

Constraints:
- No paragraphs, invented equations, crossed arrows, gradients, shadows, or numbered badges.
```

## UI mockup

```text
Create a realistic [mobile/desktop] UI mockup for [product]. Show the product as a usable shipped interface, not concept art.

Primary user task:
[user goal].

Screen structure:
[header/navigation], [main content], [controls], [data states], [footer/action]. Use realistic spacing, actual control patterns, and clear information hierarchy.

Visual system:
[background], [accent colors], [typography character], [density], [border/radius behavior].

Constraints:
- No futuristic HUD, floating decorative panels, illegible microtext, or impossible controls.
```

## Surgical edit

```text
Edit Image 1, which is the primary canvas.

Preserve exactly:
[identity, shape, proportions, camera angle, crop, lighting, labels, background elements].

Change only:
[one exact requested change].

Integration:
Match the original perspective, scale, occlusion, shadows, color temperature, texture, and image quality.

Constraints:
Keep everything else unchanged. Do not add text, accessories, objects, or style changes.
```

## Multi-image compositing

```text
Image 1 is the primary scene and camera reference. Image 2 provides [person/product/object]. Image 3 provides [material/style/layout only].

Place [element from Image 2] at [precise location in Image 1]. Apply only [specific property] from Image 3.

Preserve Image 1's framing, background, geometry, and all unrelated objects. Match perspective, scale, lighting, shadows, reflections, and occlusion so the result appears naturally captured in the original scene.

Do not change anything else.
```

## Text localization edit

```text
Translate only the visible text in Image 1 from [source language] to [target language].

Replacement map:
- "[source copy]" → "[exact target copy]"

Preserve exactly:
Typography style, placement, line hierarchy, spacing, colors, imagery, icons, logos, layout, and crop.

Do not add words, omit words, redesign the layout, or alter non-text elements.
```
