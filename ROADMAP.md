# a0-comms Roadmap

## Phased Implementation Plan

| Phase | Name | Deliverables | Testing |
|---|---|---|---|
| **1** | Mailbox Core | send/check/reply tool actions, JSONL storage, message schema, `messenger` tool registration | Unit tests for JSONL read/write, integration test: conductor sends to self |
| **2** | Live Delivery | Session registry (in-memory), direct injection via `AgentContext.communicate()`, async fallback, `list_sessions` | Test live delivery between 2 active sessions (conductor + a0-circuit:default), test fallback when session offline |
| **3** | Session Switching | `switch_session` action, spawn agent sessions under projects, timeout handling, response return to conductor | Conductor spawns a0-circuit:default with "run ls", gets response; test timeout behavior |
| **4** | Agent-to-Agent Comms | Cross-project messaging, permissions system, auto-inbox check via `agent_loop_end` extension, `broadcast` action | a0-evol:default sends to a0-circuit:default, verify receipt; broadcast to all projects |
| **5** | Configuration & Security | Config page (webui/config.html), per-project/agent scoping, cross-project isolation rules, settings resolution | Test per-project override of agent_capabilities, test cross-project blocking |
| **6** | Testing with Real Agents | End-to-end scenarios using actual projects and agents | Full workflow: conductor → spawn a0-circuit → evol sends update → conductor forwards → reply chain |
| **7** | Telegram UX Polish | Natural language routing, inbox summaries (compact/detailed/per-project), command prefix handling | Test from Telegram: "/sw a0-circuit", "check inbox", implicit routing with current_session |
| **8** | Documentation & Polish | README, usage examples, gotchas, plugin submission prep | Review against a0-review-plugin skill checklist |

## Detailed Testing Plan

**Test Projects Available:**
- `a0-circuit` (conductor profile, falke_dna, skills)
- `a0-evol` (evol agent)
- Main conductor session (global)

**Key Test Scenarios:**
1. Conductor sends async message to a0-circuit:default → a0-circuit checks inbox → replies
2. Conductor spawns a0-circuit:default via switch_session → injects "Run system check" → receives response within timeout
3. a0-evol:default sends message to conductor → conductor sees in inbox next turn
4. Cross-project: a0-evol sends to a0-circuit (if permissions allow)
5. Timeout: switch_session with 5s timeout on long task → conductor gets timeout notification, returns home
6. Forward: conductor forwards message from a0-evol inbox to a0-circuit inbox
7. Broadcast: conductor broadcasts "Health check" to all project sessions
8. Parallel sessions: conductor sets current_session=a0-circuit, then explicitly sends to a0-evol without switching
9. Auto-inbox: a0-circuit agent completes task, auto-check extension finds new message, processes it
10. Routing modes: test auto (current_session set), explicit (no current_session, must specify target), split (asks which session)
