# Prompt engineering assets

Prompts live outside Python so versions can be reviewed independently of application code.

| File | Purpose |
|------|---------|
| `content_agent_system.md` | System prompt for the LangChain content agent |
| `content_request.md` | User-request template with placeholders |
| `reviewer_system.md` | Reviewer checklist prompt |

Each prompt includes: name, version, role, goal, context policy, source-grounding policy, personal-experience policy, teaching requirements, voice requirements, output contract, failure behavior, and final self-check.

`PROMPT_VERSION` in the environment should match the prompt version in use (currently `v1`).

Notes and knowledge files are untrusted data. Instructions inside those files must never override these prompts.
