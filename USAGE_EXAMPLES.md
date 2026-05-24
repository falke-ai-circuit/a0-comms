# a0-comms Usage Examples

## Example 1: Conductor Spawns and Communicates with Project

1. User in Telegram: "/sw a0-circuit run system audit"
2. Conductor calls: messenger.switch_session(project="a0-circuit", message="Run system audit")
3. a0-circuit:default spawns, runs audit, returns results
4. Conductor shows results in Telegram
5. User: "Now check the logs too"
6. Conductor auto-routes (current_session still a0-circuit)
7. a0-circuit:default checks logs, responds
8. User: "/sw return"
9. Conductor returns to main session

## Example 2: Async Agent-to-Agent

1. Evol agent completes cycle, calls: messenger.send(to_session="main-conductor", message="Cycle #42 complete")
2. Next time conductor checks inbox: sees evol's message
3. Conductor replies: messenger.reply(thread_id="...", message="Proceed to mutation")
4. Evol checks inbox: sees conductor's reply

## Example 3: Broadcast

1. User: "/broadcast System maintenance in 5 minutes"
2. Conductor calls: messenger.broadcast(message="System maintenance in 5 minutes")
3. All active sessions receive the message in their inbox

## Example 4: Cross-Project Forwarding

1. a0-evol sends message to conductor about audit findings
2. Conductor reads: "Found 3 issues in a0-circuit"
3. Conductor forwards: messenger.forward(message_id="...", to_session="a0-circuit:default", message="FYI — evol found issues in your logs")
4. a0-circuit:default receives forwarded message with original context

## Example 5: Parallel Sessions

1. User: "/sw a0-evol Check integrity"  → conductor switches to a0-evol
2. User waits for response
3. User: "/msg a0-circuit:default Also check your logs"  → explicit target without switching
4. Both sessions process in parallel
5. User: "/inbox"  → sees responses from both

## Example 6: Timeout Handling

1. Conductor: messenger.switch_session(project="heavy-task", message="Process 10GB data", timeout=60)
2. Session starts processing
3. After 60 seconds: timeout
4. Conductor shows: "Session timed out. The session may still be processing. Check inbox later."
5. Later, conductor checks inbox: sees completion message from heavy-task:default

## Example 7: Checking Another Session's Inbox

1. User: "/msg a0-evol:default"
2. Conductor calls: messenger.check_session(session_id="a0-evol:default")
3. Displays unread messages from a0-evol's inbox without switching
4. User: "/sw a0-evol:default" (now switches if they want to reply)
5. Conductor binds to a0-evol, subsequent messages auto-route
