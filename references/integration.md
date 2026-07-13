# Agent integration

## Installation locations

- Standard user skill: `~/.agents/skills/image2-api/`
- Claude Code user skill: `~/.claude/skills/image2-api/`
- Standard project skill: `<project>/.agents/skills/image2-api/`
- Claude Code project skill: `<project>/.claude/skills/image2-api/`

Use `scripts/install_skill.py`. The parent directory must remain `image2-api` because Agent Skills requires it to match the frontmatter name.

## Selection behavior

Load this skill for explicit API/relay work, not for every image request. See `agent-routing.md` and evaluate the frontmatter against `evals/trigger-cases.json` after changing the description.

Recommended explicit invocation:

```text
Use the image2-api skill with my OpenAI-compatible relay. Compile and strictly review a GPT Image 2 project-hero prompt, perform a dry run, generate four medium-quality candidates sequentially, inspect them, and refine the selected candidate at high quality.
```

Prompt-only invocation:

```text
Use image2-api to normalize and strictly review this prompt for my GPT Image 2 API workflow. Do not make a network request.
```

Edit invocation:

```text
Use image2-api. Image 1 is the primary canvas and Image 2 is the identity reference. Preserve identity, silhouette, proportions, pose, camera angle, and crop. Change only the environment. Keep everything else unchanged.
```

## Agent execution contract

The host Agent should:

1. determine whether the API activation boundary is met;
2. choose generate, edit, prompt-only, or diagnostic mode;
3. create a structured brief or direct prompt;
4. run local prompt review;
5. perform a dry run for new relay configurations;
6. execute only when the user requested a live API action and credentials are available;
7. inspect actual images when vision is available;
8. return final paths, run directory, review status, and any provider limitation.

The Agent must distinguish a dry run from successful live generation.

## Progressive reference loading

Load `SKILL.md` first. Open only one-level reference files needed for the current subtask. Avoid loading all prompt recipes, API notes, and troubleshooting material into context at once.
