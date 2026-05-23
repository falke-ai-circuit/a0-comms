# a0-comms Gotchas

## Session ID Format
- MUST use colon separator: `project:agent`
- DO NOT use slashes or hyphens in the session ID portion
- Examples: `a0-circuit:default`, `main-conductor`, `my-project:shadow`

## Live Delivery Races
- If recipient agent is mid-turn, live injection may fail
- Plugin automatically falls back to async mailbox in this case
- Messages delivered via fallback show mode="async_fallback" in schema

## Mailbox File I/O
- JSONL files are append-only for writes
- On check (mark_read=true), the entire file is rewritten
- This means: don't have two processes writing to the same mailbox simultaneously
- For high-frequency messaging, consider batching or using a different storage backend

## Registry Ephemeral
- Session registry is IN-MEMORY only
- Container restart = all active session tracking lost
- Messages in mailboxes persist (JSONL files on disk)
- After restart, agents can still check inboxes and receive queued messages

## Cross-Project Security
- Default config allows all cross-project messages (allowed_cross_project_messages: ["*"])
- Lock down in production: specify explicit project pairs
- Example: `["a0-circuit<>a0-evol"]` allows only those two to communicate

## Timeout vs Completion
- switch_session timeout does NOT kill the spawned session
- Session continues processing after timeout
- Always check inbox later for completion message
- Use timeout as "max wait for synchronous response", not as session kill switch

## Agent Capabilities
- Capabilities are per agent PROFILE, not per session
- Multiple sessions using the same profile share the same capability set
- Override per-project or per-agent via config.json scoping

## Prompt Injection
- Messages are passed as plain text
- No sanitization is performed — trust the sender
- In cross-project scenarios, validate message sources before acting on them
- Consider adding a trusted_senders list in future versions
