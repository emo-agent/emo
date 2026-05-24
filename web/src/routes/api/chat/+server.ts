import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { spawn } from 'child_process';

export interface ChatRequestBody {
	sessionId: string;
	messages: { role: string; content: string }[];
}

export const POST: RequestHandler = async ({ request }) => {
	const body = (await request.json()) as ChatRequestBody;
	const messages = body.messages ?? [];

	// The last message is always the user message
	const lastUser = messages.findLast((m) => m.role === 'user');
	if (!lastUser) {
		return error(400, 'No user message provided');
	}

	// Build context: include prior conversation as context in the prompt
	// For now, send the full history as a single prompt with role prefixes
	const historyContext = messages
		.slice(0, -1) // everything except the last user message
		.map((m) => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`)
		.join('\n');

	const prompt = historyContext
		? `Previous conversation:\n${historyContext}\n\nUser: ${lastUser.content}`
		: lastUser.content;

	// Find the emo executable — prefer the venv in the repo root
	const emoRoot = process.env.EMO_ROOT ?? new URL('../../../../..', import.meta.url).pathname;
	const emoBin = `${emoRoot}/.venv/bin/emo`;

	const stream = new ReadableStream({
		start(controller) {
			const proc = spawn(emoBin, ['-m', prompt, '--no-supervisor'], {
				cwd: emoRoot,
				env: {
					...process.env,
					PYTHONUNBUFFERED: '1'
				}
			});

			proc.stdout.on('data', (chunk: Buffer) => {
				controller.enqueue(chunk);
			});

			proc.stderr.on('data', (_chunk: Buffer) => {
				// suppress stderr from the subprocess
			});

			proc.on('close', (code) => {
				if (code !== 0 && code !== null) {
					controller.enqueue(
						Buffer.from(`\n[emo exited with code ${code}]`)
					);
				}
				controller.close();
			});

			proc.on('error', (err) => {
				controller.enqueue(Buffer.from(`Error starting emo: ${err.message}`));
				controller.close();
			});
		}
	});

	return new Response(stream, {
		headers: {
			'Content-Type': 'text/plain; charset=utf-8',
			'Transfer-Encoding': 'chunked',
			'Cache-Control': 'no-cache'
		}
	});
};
