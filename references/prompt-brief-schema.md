# Structured prompt brief schema

`scripts/build_prompt.py` accepts a JSON object and compiles it into a readable GPT Image 2 prompt. The schema is intentionally permissive so Agents can omit irrelevant fields.

## Common fields

```json
{
  "profile": "project-hero",
  "operation": "generate",
  "deliverable": "16:9 repository hero",
  "purpose": "GitHub README and social preview",
  "audience": "Developers evaluating the project",
  "scene": "Environment or background before the subject",
  "subject": "Main subject identity and appearance",
  "action": "Pose, gaze, motion, or interaction",
  "key_details": ["Required object or visual fact"],
  "composition": "Framing, placement, hierarchy, negative space",
  "camera": "Viewpoint and high-level photographic language",
  "style": "Coherent visual medium and art direction",
  "materials": "Surface and material language",
  "lighting": "Direction, softness, contrast, atmosphere",
  "palette": "Named colors or color roles",
  "text": {
    "exact": ["Literal copy"],
    "placement": "Where it appears",
    "language": "English",
    "spelling": "T-e-c-h-D-o-u"
  },
  "typography": "Font character, weight, scale, contrast",
  "references": {
    "Image 1": "Primary canvas and identity",
    "Image 2": "Style reference only"
  },
  "preserve": ["Edit invariant"],
  "changes": ["Only requested change"],
  "constraints": ["Positive requirement"],
  "avoid": ["Natural-language exclusion"]
}
```

## Profiles

List supported profiles:

```bash
python scripts/build_prompt.py --list-profiles
```

Print the current schema:

```bash
python scripts/build_prompt.py --print-schema
```

Compile and review:

```bash
python scripts/build_prompt.py \
  --brief examples/briefs/open-source-project-hero.json \
  --profile project-hero \
  --lint \
  --output prompt.txt
```

Strict mode fails on warnings and is useful in tests or controlled pipelines:

```bash
python scripts/build_prompt.py \
  --brief brief.json \
  --strict \
  --json
```

## Text field forms

No text:

```json
{"text": "No text"}
```

Single exact line:

```json
{
  "text": {
    "exact": ["VibeCanvas"],
    "placement": "Centered in the right text-safe region",
    "language": "English",
    "spelling": "V-i-b-e-C-a-n-v-a-s"
  }
}
```

Several lines:

```json
{
  "text": {
    "exact": ["VibeCanvas", "Agent-native image workflows"],
    "hierarchy": "Project name large; descriptor smaller",
    "placement": "Right side"
  }
}
```

## Edit brief

```json
{
  "profile": "edit",
  "operation": "edit",
  "deliverable": "Reference-preserving background replacement",
  "references": {
    "Image 1": "Primary canvas and exact character identity",
    "Image 2": "Background material reference only"
  },
  "preserve": [
    "face, silhouette, body proportions, clothing, pose, camera angle, and crop"
  ],
  "changes": [
    "replace only the background with a warm ceramic technology studio"
  ],
  "constraints": [
    "match the original subject lighting",
    "keep everything else unchanged"
  ]
}
```
