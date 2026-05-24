# a0-comms — Inter-Session Messenger for Agent Zero

Lightweight message bus linking Agent Zero sessions across projects, agents, and time.
Conductor becomes central command — spawn, message, monitor any session.

## Features
- **Async Mailbox**: Send messages to any session; recipient checks inbox when ready
- **Live Delivery**: Direct injection to active sessions with async fallback
- **Session Switching**: Spawn sessions under projects and interact with them
- **Broadcast**: Send messages to all active sessions at once
- **Forwarding**: Redirect messages between sessions
- **Cross-Project**: Messages between different projects with permission control
- **Auto-Inbox**: Extension automatically checks for new messages
- **Telegram Ready**: Natural language command routing for Telegram bot integration

## Installation
1. Copy to `/a0/usr/plugins/a0_comms/`
2. Ensure plugin is enabled (Settings → Plugins)
3. Configure per-agent capabilities if needed

## Usage

### Agent Tool
Agents use the `messenger` tool with actions:

```json
{"action": "send", "to_session": "a0-evol:default", "message": "Audit complete"}
{"action": "check"}
{"action": "reply", "thread_id": "...", "message": "Proceed"}
{"action": "list_sessions"}
{"action": "switch_session", "project": "a0-circuit", "message": "Run audit"}
{"action": "broadcast", "message": "Health check"}
{"action": "forward", "message_id": "...", "to_session": "other-project:default"}
{"action": "check_session", "session_id": "a0-evol:default"}
```

### Conductor Commands (Telegram)
```
/sw a0-circuit             — bind telegram to a0-circuit session
/sw return                 — return to main conductor
/sw list                   — list all sessions
/sw multi                  — activate all sessions, consolidated view
/msg a0-evol:default Audit — send message without switching
/msg a0-evol:default       — read that session's inbox
/inbox                     — check own inbox
/reply 3 yes proceed       — reply to message #3
/forward 5 a0-circuit      — forward message #5
/broadcast Health check    — send to all
```

## Session ID Convention
Semantic format: `project:agent_profile`
- `a0-circuit:default` — project's default agent
- `a0-evol:default` — evol agent
- `main-conductor` — global conductor session

## Configuration
14 settings available via plugin config page:

| Setting | Default | Description |
|---|---|---|
| default_routing_mode | auto | auto/explicit/split |
| default_timeout_seconds | 120 | Spawn session timeout |
| auto_check_inbox | true | Auto-check inbox each turn |
| auto_route_after_response | true | Prompt "continue?" after session response |
| agent_capabilities | (tiered) | Per-profile action permissions |
| allowed_cross_project_messages | * | Cross-project message pairs |
| stale_session_timeout | 300 | Registry stale timeout |
| live_delivery_enabled | true | Direct injection to live sessions |
| live_delivery_fallback | true | Fallback to async if live fails |
| mailbox_max_messages_per_check | 20 | Max messages per inbox check |
| message_retention_days | 30 | Auto-delete old messages |
| notification_on_new_message | true | WebUI toast notifications |
| command_prefix | / | Telegram command prefix |
| inbox_summary_style | compact | compact/detailed/per-project |

## Agent Capabilities
| Profile | send | check | reply | list | switch | broadcast | forward |
|---|---|---|---|---|---|---|---|
| conductor | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| default | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| evol | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| coder | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| reviewer | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| orchestrator | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| shadow | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |

## Architecture

### Components
- **Message Bus**: Routes messages; decides direct vs async
- **Session Registry**: In-memory map of active sessions with stale timeout
- **Mailbox Store**: JSONL per session under `mailboxes/<session_id>.jsonl`
- **Router**: Resolves semantic session IDs to live context_ids or mailbox paths
- **Delivery Manager**: Direct injection via AgentContext.communicate() with async fallback
- **Telegram Adapter**: Built-in; conductor handles translation

### Message Flow
1. **Async**: Send → write to recipient JSONL → recipient checks inbox → reads & replies
2. **Direct**: Send → check registry → inject via AgentContext.communicate() → fallback to async
3. **Session Switch**: Spawn → inject message → wait for response → return to conductor

## Testing
```bash
cd /a0/usr/projects/a0-comms
python -m pytest tests/ -v
```

## Gotchas
- Session IDs use colon separator: `project:agent`
- Live delivery may fail if recipient is mid-turn; falls back to async automatically
- Mailbox files are JSONL — append-only for writes, full rewrite on check (mark read)
- Registry is in-memory only; restarts lose active session tracking
- Cross-project messaging requires allowed_cross_project_messages config

## License
MIT
