# a0-comms Blueprint

## 1. Plugin Concept
Inter-session/inter-agent/inter-project messaging plugin. Conductor (Telegram) as central command — spawn, message, monitor any session. Both direct (live) and async (mailbox) delivery.

## 2. Components
| Component | Role |
|---|---|
| Message Bus | Routes messages between sessions; decides direct vs async |
| Session Registry | In-memory map: session_id → (context_id, last_seen, project, agent). 5-min stale timeout |
| Mailbox Store | JSONL per session under `mailboxes/<session_id>.jsonl` |
| Router | Resolves semantic session IDs (`project:agent`) to live context_ids or mailbox paths |
| Delivery Manager | Direct injection via `AgentContext.communicate()` with async fallback |
| Telegram Adapter | Built-in; conductor handles all Telegram translation (no separate bridge) |

## 3. Session ID Convention: Semantic
| Format | Example |
|---|---|
| Full | `a0-circuit:conductor` |
| Project-default | `a0-circuit:default` |
| Global | `main-conductor` |

## 4. Tool API: `messenger` tool
All operations through single tool with `action` parameter:

| Action | Args | Returns |
|---|---|---|
| `send` | to_session, message, mode=async | message_id |
| `check` | (none) | list of unread messages |
| `reply` | thread_id, message | message_id |
| `list_sessions` | (none) | list of known session IDs with status |
| `switch_session` | project, agent_profile, message, timeout=120 | response + new session_id |
| `broadcast` | message, projects=[] | list of message_ids |
| `forward` | message_id, to_session | new message_id |

## 5. Message Schema
```json
{
  "message_id": "uuid",
  "thread_id": "uuid",
  "from_session": "session_id",
  "to_session": "session_id",
  "from_agent": "agent_profile",
  "timestamp": "iso8601",
  "status": "unread|read",
  "mode": "direct|async|async_fallback",
  "content": "text"
}
```

## 6. Message Flow
1. **Async (Mailbox)**: Send → write to recipient JSONL → recipient checks inbox → reads & replies
2. **Direct (Live)**: Send → check registry for live context_id → inject via `AgentContext.communicate()` → fallback to async if fails
3. **Session Switching**: Conductor calls `switch_session` → spawns agent session under project → injects message → waits for response (with timeout) → returns response to conductor

## 7. Conductor State Management
Conductor maintains routing state via `memory_save`:
```json
{
  "routing_table": {
    "a0-circuit": {"session_id": "a0-circuit:default", "context_id": "...", "last_seen": "..."},
    "a0-evol": {"session_id": "a0-evol:default", "context_id": "...", "last_seen": "..."}
  },
  "current_session": "a0-circuit:default"
}
```
When `current_session` is set, all user messages auto-route to that session. User can override with explicit target ("Tell a0-evol to X"). Routing modes: `auto`, `explicit`, `split` (configurable).

## 8. Agent Capabilities (Tiered)
| Profile | send | check | reply | list_sessions | switch_session | broadcast | forward |
|---|---|---|---|---|---|---|---|
| conductor | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| default | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| evol | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| coder | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| reviewer | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| orchestrator | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| shadow | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |

## 9. Cross-Project Messaging
Controlled by `allowed_cross_project_messages` config. Default: `["*"]` (all allowed). Can restrict to specific project pairs.

## 10. Plugin Directory Structure
```
/a0/usr/plugins/a0_comms/
├── plugin.yaml
├── default_config.yaml
├── tools/
│   └── messenger.py
├── helpers/
│   ├── bus.py
│   ├── registry.py
│   ├── mailbox.py
│   └── session_manager.py
├── extensions/
│   └── python/
│       └── agent_loop_end/
│           └── __init__.py
├── webui/
│   └── config.html
└── README.md
```
