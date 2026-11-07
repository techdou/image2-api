# Selection and routing fixtures

`trigger-cases.json` covers API and relay requests, ordinary host image tasks, local conversion, and precise diagrams. Use the development cases to revise the description and keep the holdout cases for a fresh check.

1. Start a fresh session for each prompt with the skill discoverable. Prepend the optional `context` as prior conversation. Pass only the prompt and its context. Keep `expected`, `route`, and fixture IDs out of the agent's input.
2. Record whether the agent loaded `SKILL.md` and compare that with `expected`. For a host-level trigger rate, repeat each prompt in the target host and report both missed activations and false activations.
3. For selected cases, inspect the proposed or observed action against `route`. Check operation, network mode, requested format and any specified transport or parameters. `blocked` means the requested constraints conflict with the supported API path. Verify that no live call is proposed for that case.
4. Use a mock provider or inspect the proposed call for cases labeled `network: live`. Do not spend provider credits to score a routing case.

The package validator checks fixture structure. Running it alone does not measure host-level matching or tool choice.
