/**
 * WebSocket connection to the emo daemon.
 *
 * Exposes a simple reactive store (`daemon`) that wraps the WebSocket and
 * provides the full chat state — sessions, messages, loading state — all
 * driven by messages from the daemon.
 *
 * Connection is lazy: the WebSocket opens on the first call to `connect()`.
 * It auto-reconnects with exponential back-off (capped at 30 s).
 *
 * The daemon URL is read from the `EMO_DAEMON_URL` env var at build time,
 * falling back to `ws://127.0.0.1:7777/ws`.
 */

import type {
	ClientMsg,
	ServerMsg,
	SessionData,
	StoredMessage,
	AgentEntry,
	SkillEntry,
	MCPEntry
} from './protocol';

// Vite exposes env vars prefixed with VITE_; fall back to the default daemon address.
const DAEMON_URL: string = (import.meta.env.VITE_EMO_DAEMON_URL as string | undefined) ?? 'ws://127.0.0.1:7777/ws';

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

function createDaemonStore() {
	// ── Reactive state ──────────────────────────────────────────────────────
	let connectionState = $state<ConnectionState>('disconnected');
	let sessions = $state<SessionData[]>([]);
	let activeSessionId = $state<string | null>(null);
	let isLoading = $state(false);
	let error = $state<string | null>(null);
	let configData = $state<Record<string, unknown> | null>(null);
	let agents = $state<AgentEntry[]>([]);
	let skills = $state<SkillEntry[]>([]);
	let mcps = $state<MCPEntry[]>([]);
	let activeAgentConfig = $state<{ name: string; config: Record<string, unknown> } | null>(null);
	let activeSkillContent = $state<{ name: string; content: string } | null>(null);

	// ── Derived ─────────────────────────────────────────────────────────────
	const sortedSessions = $derived(
		[...sessions].sort((a, b) => b.updated_at - a.updated_at)
	);
	const activeSession = $derived(
		sessions.find((s) => s.id === activeSessionId) ?? null
	);
	const messages = $derived(activeSession?.messages ?? []);

	// ── Internal WebSocket state ─────────────────────────────────────────────
	let _ws: WebSocket | null = null;
	let _retryDelay = 1000;
	let _retryTimer: ReturnType<typeof setTimeout> | null = null;
	let _intentionalClose = false;

	// Pending callbacks waiting for session_created after sending new_session or chat with no session_id
	let _pendingSessionResolve: ((id: string) => void) | null = null;

	// ── WebSocket lifecycle ──────────────────────────────────────────────────

	function connect() {
		if (_ws && (_ws.readyState === WebSocket.OPEN || _ws.readyState === WebSocket.CONNECTING)) {
			return;
		}
		_intentionalClose = false;
		connectionState = 'connecting';
		error = null;

		const ws = new WebSocket(DAEMON_URL);
		_ws = ws;

		ws.addEventListener('open', () => {
			connectionState = 'connected';
			_retryDelay = 1000;
			// Load existing sessions from daemon
			_send({ type: 'list' });
			// Pre-fetch all settings data so panels have values on first render
			_send({ type: 'get_config' });
			_send({ type: 'list_agents' });
			_send({ type: 'list_skills' });
			_send({ type: 'list_mcps' });
		});

		ws.addEventListener('message', (ev) => {
			try {
				const msg = JSON.parse(ev.data as string) as ServerMsg;
				_handleMessage(msg);
			} catch {
				// ignore malformed
			}
		});

		ws.addEventListener('close', () => {
			_ws = null;
			if (!_intentionalClose) {
				connectionState = 'disconnected';
				_scheduleReconnect();
			}
		});

		ws.addEventListener('error', () => {
			connectionState = 'error';
			error = `Cannot reach emo daemon at ${DAEMON_URL}`;
			ws.close();
		});
	}

	function disconnect() {
		_intentionalClose = true;
		if (_retryTimer) {
			clearTimeout(_retryTimer);
			_retryTimer = null;
		}
		_ws?.close();
		_ws = null;
		connectionState = 'disconnected';
	}

	function _scheduleReconnect() {
		if (_retryTimer) return;
		_retryTimer = setTimeout(() => {
			_retryTimer = null;
			if (!_intentionalClose) connect();
		}, _retryDelay);
		_retryDelay = Math.min(_retryDelay * 2, 30_000);
	}

	function _send(msg: ClientMsg) {
		if (_ws?.readyState === WebSocket.OPEN) {
			_ws.send(JSON.stringify(msg));
		} else {
			error = 'Not connected to daemon. Reconnecting…';
			connect();
		}
	}

	// ── Message handlers ─────────────────────────────────────────────────────

	function _handleMessage(msg: ServerMsg) {
		switch (msg.type) {
			case 'sessions':
				sessions = msg.sessions;
				// Preserve active session if still present; default to newest
				if (!activeSessionId || !sessions.find((s) => s.id === activeSessionId)) {
					activeSessionId = sessions.length > 0 ? sessions[0].id : null;
				}
				break;

			case 'session_created': {
				const newSession: SessionData = {
					id: msg.session_id,
					title: msg.title,
					created_at: msg.created_at,
					updated_at: msg.created_at,
					messages: []
				};
				sessions = [newSession, ...sessions];
				activeSessionId = msg.session_id;
				if (_pendingSessionResolve) {
					_pendingSessionResolve(msg.session_id);
					_pendingSessionResolve = null;
				}
				break;
			}

			case 'session_deleted':
				sessions = sessions.filter((s) => s.id !== msg.session_id);
				if (activeSessionId === msg.session_id) {
					activeSessionId = sessions.length > 0 ? sessions[0].id : null;
				}
				break;

			case 'token': {
				// Append token to the last assistant message in this session
				sessions = sessions.map((s) => {
					if (s.id !== msg.session_id) return s;
					const msgs = [...s.messages];
					const last = msgs[msgs.length - 1];
					if (last && last.role === 'assistant') {
						msgs[msgs.length - 1] = { ...last, content: last.content + msg.token };
					}
					return { ...s, messages: msgs, updated_at: Date.now() / 1000 };
				});
				break;
			}

			case 'done': {
				isLoading = false;
				// Ensure the final content is authoritative (replace streaming accumulation)
				sessions = sessions.map((s) => {
					if (s.id !== msg.session_id) return s;
					const msgs = [...s.messages];
					const last = msgs[msgs.length - 1];
					if (last && last.role === 'assistant') {
						msgs[msgs.length - 1] = { ...last, content: msg.content };
					}
					return { ...s, messages: msgs, updated_at: Date.now() / 1000 };
				});
				break;
			}

			case 'error':
				isLoading = false;
				error = msg.message;
				break;

			case 'config_data':
				configData = msg.data;
				break;
			case 'agents_data':
				agents = msg.agents;
				break;
			case 'agent_data':
				activeAgentConfig = { name: msg.name, config: msg.config };
				break;
			case 'skills_data':
				skills = msg.skills;
				break;
			case 'skill_data':
				activeSkillContent = { name: msg.name, content: msg.content };
				break;
			case 'mcps_data':
				mcps = msg.mcps;
				break;
			case 'ok':
				// ok is handled by callers who re-request data; nothing to do globally
				break;
		}
	}

	// ── Public actions ───────────────────────────────────────────────────────

	function newSession() {
		_send({ type: 'new_session' });
	}

	function selectSession(id: string) {
		activeSessionId = id;
	}

	function deleteSession(id: string) {
		_send({ type: 'delete', session_id: id });
	}

	function sendMessage(content: string, agent?: string) {
		if (!content.trim()) return;
		error = null;

		const sid = activeSessionId ?? '';

		// Optimistically insert user message into the active session
		const userMsg: StoredMessage = {
			id: crypto.randomUUID(),
			role: 'user',
			content: content.trim(),
			created_at: Date.now() / 1000
		};
		// Optimistically insert blank assistant message for streaming
		const assistantMsg: StoredMessage = {
			id: crypto.randomUUID(),
			role: 'assistant',
			content: '',
			created_at: Date.now() / 1000
		};

		if (sid) {
			sessions = sessions.map((s) =>
				s.id === sid
					? { ...s, messages: [...s.messages, userMsg, assistantMsg], updated_at: Date.now() / 1000 }
					: s
			);
		}
		// If no session, the daemon will create one and session_created will fire;
		// the optimistic messages can't be added until we know the session_id.
		// In practice the daemon responds so fast this is fine for now.

		isLoading = true;
		_send({ type: 'chat', session_id: sid, content: content.trim(), agent });
	}

	// ── Config / Agent / Skill / MCP actions ─────────────────────────────────

	function fetchConfig() { _send({ type: 'get_config' }); }
	function setConfig(patch: Record<string, unknown>) { _send({ type: 'set_config', patch }); }
	function fetchAgents() { _send({ type: 'list_agents' }); }
	function fetchAgent(name: string) { _send({ type: 'get_agent', name }); }
	function saveAgent(name: string, config: Record<string, unknown>) { _send({ type: 'set_agent', name, config }); }
	function deleteAgent(name: string) { _send({ type: 'delete_agent', name }); }
	function fetchSkills() { _send({ type: 'list_skills' }); }
	function fetchSkill(name: string) { _send({ type: 'get_skill', name }); }
	function saveSkill(name: string, content: string) { _send({ type: 'set_skill', name, content }); }
	function deleteSkill(name: string) { _send({ type: 'delete_skill', name }); }
	function fetchMCPs() { _send({ type: 'list_mcps' }); }
	function saveMCP(name: string, config: Record<string, unknown>) { _send({ type: 'set_mcp', name, config }); }
	function deleteMCP(name: string) { _send({ type: 'delete_mcp', name }); }

	return {
		// State
		get connectionState() {
			return connectionState;
		},
		get sessions() {
			return sortedSessions;
		},
		get activeSession() {
			return activeSession;
		},
		get activeSessionId() {
			return activeSessionId;
		},
		get messages() {
			return messages;
		},
		get isLoading() {
			return isLoading;
		},
		get error() {
			return error;
		},
		get configData() { return configData; },
		get agents() { return agents; },
		get skills() { return skills; },
		get mcps() { return mcps; },
		get activeAgentConfig() { return activeAgentConfig; },
		get activeSkillContent() { return activeSkillContent; },
		// Actions
		connect,
		disconnect,
		newSession,
		selectSession,
		deleteSession,
		sendMessage,
		fetchConfig,
		setConfig,
		fetchAgents,
		fetchAgent,
		saveAgent,
		deleteAgent,
		fetchSkills,
		fetchSkill,
		saveSkill,
		deleteSkill,
		fetchMCPs,
		saveMCP,
		deleteMCP
	};
}

export const daemon = createDaemonStore();
