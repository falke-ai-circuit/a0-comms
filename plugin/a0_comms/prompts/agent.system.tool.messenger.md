## messenger tool
send messages between agent sessions via async mailbox
args: `action`, optional `to_session`, `message`, `thread_id`, `limit`
actions:
- `send`: send message to another session's mailbox. requires `to_session` and `message`. returns message_id
- `check`: check own session's mailbox for unread messages. optional `limit` (default 20). returns list of messages with IDs and thread IDs
- `reply`: reply to a message thread. requires `thread_id` and `message`. looks up original sender and routes reply
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
