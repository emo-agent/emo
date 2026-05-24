export type Role = 'user' | 'assistant';

export interface ChatMessage {
	id: string;
	role: Role;
	content: string;
	createdAt: Date;
}

export interface ChatSession {
	id: string;
	title: string;
	createdAt: Date;
	updatedAt: Date;
	messages: ChatMessage[];
}

function generateId(): string {
	return crypto.randomUUID();
}

function deriveTitle(messages: ChatMessage[]): string {
	const first = messages.find((m) => m.role === 'user');
	if (!first) return 'New Chat';
	return first.content.slice(0, 60) + (first.content.length > 60 ? '…' : '');
}

function loadSessions(): ChatSession[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem('emo:sessions');
		if (!raw) return [];
		const parsed = JSON.parse(raw) as ChatSession[];
		return parsed.map((s) => ({
			...s,
			createdAt: new Date(s.createdAt),
			updatedAt: new Date(s.updatedAt),
			messages: s.messages.map((m) => ({ ...m, createdAt: new Date(m.createdAt) }))
		}));
	} catch {
		return [];
	}
}

function saveSessions(sessions: ChatSession[]) {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem('emo:sessions', JSON.stringify(sessions));
}

function createChatStore() {
	const initial = loadSessions();
	let sessions = $state<ChatSession[]>(initial);
	let activeSessionId = $state<string | null>(initial[0]?.id ?? null);
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	const activeSession = $derived(sessions.find((s) => s.id === activeSessionId) ?? null);
	const messages = $derived(activeSession?.messages ?? []);
	const sortedSessions = $derived(
		[...sessions].sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
	);

	function newSession(): string {
		const id = generateId();
		const session: ChatSession = {
			id,
			title: 'New Chat',
			createdAt: new Date(),
			updatedAt: new Date(),
			messages: []
		};
		sessions = [session, ...sessions];
		activeSessionId = id;
		saveSessions(sessions);
		return id;
	}

	function selectSession(id: string) {
		activeSessionId = id;
	}

	function deleteSession(id: string) {
		sessions = sessions.filter((s) => s.id !== id);
		if (activeSessionId === id) {
			activeSessionId = sessions[0]?.id ?? null;
		}
		saveSessions(sessions);
	}

	function renameSession(id: string, title: string) {
		sessions = sessions.map((s) => (s.id === id ? { ...s, title } : s));
		saveSessions(sessions);
	}

	async function sendMessage(content: string) {
		if (!content.trim()) return;

		let sessionId = activeSessionId;
		if (!sessionId) {
			sessionId = newSession();
		}

		const userMsg: ChatMessage = {
			id: generateId(),
			role: 'user',
			content: content.trim(),
			createdAt: new Date()
		};

		sessions = sessions.map((s) =>
			s.id === sessionId
				? {
						...s,
						messages: [...s.messages, userMsg],
						title: s.messages.length === 0 ? deriveTitle([userMsg]) : s.title,
						updatedAt: new Date()
					}
				: s
		);
		saveSessions(sessions);

		isLoading = true;
		error = null;

		try {
			const history = sessions.find((s) => s.id === sessionId)?.messages ?? [];
			const response = await fetch('/api/chat', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					sessionId,
					messages: history.map((m) => ({ role: m.role, content: m.content }))
				})
			});

			if (!response.ok) {
				const text = await response.text();
				throw new Error(text || `HTTP ${response.status}`);
			}

			const assistantMsg: ChatMessage = {
				id: generateId(),
				role: 'assistant',
				content: '',
				createdAt: new Date()
			};

			sessions = sessions.map((s) =>
				s.id === sessionId
					? { ...s, messages: [...s.messages, assistantMsg], updatedAt: new Date() }
					: s
			);

			// Stream response
			const reader = response.body?.getReader();
			const decoder = new TextDecoder();

			if (reader) {
				while (true) {
					const { done, value } = await reader.read();
					if (done) break;
					const chunk = decoder.decode(value, { stream: true });
					sessions = sessions.map((s) =>
						s.id === sessionId
							? {
									...s,
									messages: s.messages.map((m) =>
										m.id === assistantMsg.id ? { ...m, content: m.content + chunk } : m
									),
									updatedAt: new Date()
								}
							: s
					);
				}
			}

			saveSessions(sessions);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			isLoading = false;
		}
	}

	return {
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
		newSession,
		selectSession,
		deleteSession,
		renameSession,
		sendMessage
	};
}

export const chat = createChatStore();
