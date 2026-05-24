/**
 * Typed protocol matching emo/daemon/protocol.py
 */

// Client → Server
export interface PairRequestMsg {
	type: 'pair_request';
	token?: string; // bearer token from a previous pairing; omit on first connect
}

export interface PairPinMsg {
	type: 'pair_pin';
	pin: string;
}

export interface ChatMsg {
	type: 'chat';
	session_id: string; // empty string = auto-create
	content: string;
	agent?: string;
}

export interface NewSessionMsg {
	type: 'new_session';
}

export interface ListMsg {
	type: 'list';
}

export interface DeleteMsg {
	type: 'delete';
	session_id: string;
}

export type GetConfigMsg = { type: 'get_config' };
export type SetConfigMsg = { type: 'set_config'; patch: Record<string, unknown> };
export type ListAgentsMsg = { type: 'list_agents' };
export type GetAgentMsg = { type: 'get_agent'; name: string };
export type SetAgentMsg = { type: 'set_agent'; name: string; config: Record<string, unknown> };
export type DeleteAgentMsg = { type: 'delete_agent'; name: string };
export type ListSkillsMsg = { type: 'list_skills' };
export type GetSkillMsg = { type: 'get_skill'; name: string };
export type SetSkillMsg = { type: 'set_skill'; name: string; content: string };
export type DeleteSkillMsg = { type: 'delete_skill'; name: string };
export type ListMCPsMsg = { type: 'list_mcps' };
export type SetMCPMsg = { type: 'set_mcp'; name: string; config: Record<string, unknown> };
export type DeleteMCPMsg = { type: 'delete_mcp'; name: string };

export type ClientMsg =
	| PairRequestMsg
	| PairPinMsg
	| ChatMsg
	| NewSessionMsg
	| ListMsg
	| DeleteMsg
	| GetConfigMsg
	| SetConfigMsg
	| ListAgentsMsg
	| GetAgentMsg
	| SetAgentMsg
	| DeleteAgentMsg
	| ListSkillsMsg
	| GetSkillMsg
	| SetSkillMsg
	| DeleteSkillMsg
	| ListMCPsMsg
	| SetMCPMsg
	| DeleteMCPMsg;

// Server → Client
export interface PairChallengeMsg {
	type: 'pair_challenge';
	pin_required: boolean;
}

export interface AuthOkMsg {
	type: 'auth_ok';
	token?: string; // set only on first successful pairing
}

export interface TokenMsg {
	type: 'token';
	session_id: string;
	token: string;
}

export interface ToolMsg {
	type: 'tool';
	session_id: string;
	name: string;
	preview: string;
}

export interface DoneMsg {
	type: 'done';
	session_id: string;
	content: string;
	agent_name: string;
}

export interface ErrorMsg {
	type: 'error';
	session_id: string;
	message: string;
}

export interface SessionsMsg {
	type: 'sessions';
	sessions: SessionData[];
}

export interface SessionCreatedMsg {
	type: 'session_created';
	session_id: string;
	title: string;
	created_at: number;
}

export interface SessionDeletedMsg {
	type: 'session_deleted';
	session_id: string;
}

export type ConfigDataMsg = { type: 'config_data'; data: Record<string, unknown> };
export type AgentEntry = { name: string; config: Record<string, unknown>; source: 'user' | 'builtin' };
export type AgentsDataMsg = { type: 'agents_data'; agents: AgentEntry[] };
export type AgentDataMsg = { type: 'agent_data'; name: string; config: Record<string, unknown> };
export type SkillEntry = { name: string; summary: string };
export type SkillsDataMsg = { type: 'skills_data'; skills: SkillEntry[] };
export type SkillDataMsg = { type: 'skill_data'; name: string; content: string };
export type MCPEntry = { name: string; [key: string]: unknown };
export type MCPsDataMsg = { type: 'mcps_data'; mcps: MCPEntry[] };
export type OkMsg = { type: 'ok'; message: string };

export type ServerMsg =
	| PairChallengeMsg
	| AuthOkMsg
	| TokenMsg
	| ToolMsg
	| DoneMsg
	| ErrorMsg
	| SessionsMsg
	| SessionCreatedMsg
	| SessionDeletedMsg
	| ConfigDataMsg
	| AgentsDataMsg
	| AgentDataMsg
	| SkillsDataMsg
	| SkillDataMsg
	| MCPsDataMsg
	| OkMsg;

// Domain types
export interface StoredMessage {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	created_at: number;
}

export interface SessionData {
	id: string;
	title: string;
	created_at: number;
	updated_at: number;
	messages: StoredMessage[];
}
