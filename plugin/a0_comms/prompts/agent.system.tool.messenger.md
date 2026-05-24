## messenger tool
send messages between agent sessions via async mailbox
args: `action`, optional `to_session`, `session_id`, `message`, `thread_id`, `limit`, `project`, `agent_profile`, `timeout`
actions:
- `send`: send message to another session's mailbox. requires `to_session` and `message`. returns message_id
- `check`: check own session's mailbox for unread messages. optional `limit` (default 20). returns list of messages with IDs and thread IDs
- `check_session`: read another session's mailbox without switching. requires `session_id`. optional `limit` (default 20). returns list of unread messages
- `reply`: reply to a message thread. requires `thread_id` and `message`. looks up original sender and routes reply
- `list_sessions`: list known sessions and their live/active status. returns list of sessions
- `switch_session`: spawn a new agent session under a project and inject a message. requires `project`, `message`. optional `agent_profile` (default: "default"), `timeout` (default: 120). returns the spawned session's response.
- `broadcast`: broadcast a message to all active sessions (excluding self). requires `message`. returns count of delivered sessions.
- `forward`: forward a message from own inbox to another session. requires `message_id` and `to_session`. optional `message` (annotation prepended).

example:
~~~json
{
  "thoughts": ["Need to notify a0-evol about completed task."],
  "headline": "Sending message to a0-evol",
  "tool_name": "messenger",
  "tool_args": {
    "action": "send",
    "to_session": "a0-evol:default",
    "message": "EVOL audit phase complete. Proceed to mutation."
  }
}
~~~

- `forward`: forward a message from own inbox to another session. requires `message_id` and `to_session`. optional `message` (annotation prepended to forwarded content). preserves original thread_id.
~~~json
{
  "thoughts": ["Need to forward message to reviewer."],
  "headline": "Forwarding message to reviewer",
  "tool_name": "messenger",
  "tool_args": {
    "action": "forward",
    "message_id": "msg-abc-123",
    "to_session": "a0-circuit:reviewer",
    "message": "FYI — relevant to your review"
  }
}
~~~

- `broadcast`: broadcast a message to all active sessions (excluding self). requires `message`. returns count of delivered sessions.
~~~json
{
  "thoughts": ["Need to notify all sessions."],
  "headline": "Broadcasting alert to all sessions",
  "tool_name": "messenger",
  "tool_args": {
    "action": "broadcast",
    "message": "⚠️ System maintenance in 5 minutes."
  }
}
~~~

- `switch_session`: spawn a new agent session under a project and inject a message. requires `project`, `message`. optional `agent_profile` (default: "default"), `timeout` (default: 120). returns the spawned session's response.
~~~json
{
  "thoughts": ["Need to run audit on a0-circuit project."],
  "headline": "Spawning a0-circuit session for audit",
  "tool_name": "messenger",
  "tool_args": {
    "action": "switch_session",
    "project": "a0-circuit",
    "message": "Run full audit on evol logs."
  }
}
~~~

- `check_session`: read another session's inbox without switching sessions. requires `session_id`. optional `limit`.
~~~json
{
  "thoughts": ["Need to check a0-evol inbox without switching."],
  "headline": "Checking a0-evol inbox",
  "tool_name": "messenger",
  "tool_args": {
    "action": "check_session",
    "session_id": "a0-evol:default"
  }
}
~~~

- `list_sessions`: list known sessions and their live/active status. no required args. returns array of session objects with session_id, agent_profile, project, active_since, status.
~~~json
{
  "thoughts": ["Need to see available sessions."],
  "headline": "Listing active sessions",
  "tool_name": "messenger",
  "tool_args": {
    "action": "list_sessions"
  }
}
~~~
