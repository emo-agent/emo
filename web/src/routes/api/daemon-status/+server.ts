import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * GET /api/daemon-status
 *
 * Lightweight server-side check: attempts a TCP connection to the emo daemon
 * and returns its reachability status.  The web frontend connects via WebSocket
 * directly from the browser, but this endpoint is useful for health probes,
 * CI, and debugging.
 */
export const GET: RequestHandler = async () => {
	const host = process.env.EMO_DAEMON_HOST ?? '127.0.0.1';
	const port = parseInt(process.env.EMO_DAEMON_PORT ?? '7777', 10);

	try {
		// Use a WebSocket upgrade request as a quick reachability probe.
		// We intentionally abort immediately after getting any HTTP response.
		const controller = new AbortController();
		const timeoutId = setTimeout(() => controller.abort(), 2000);

		let reachable = false;
		try {
			const res = await fetch(`http://${host}:${port}/ws`, {
				signal: controller.signal,
				headers: { Upgrade: 'websocket' }
			});
			// Any HTTP response (even 400/426 "Upgrade Required") means the server is up
			reachable = res.status < 500;
		} catch {
			reachable = false;
		} finally {
			clearTimeout(timeoutId);
		}

		return json({
			reachable,
			host,
			port,
			url: `ws://${host}:${port}/ws`
		});
	} catch {
		return json({ reachable: false, host, port, url: `ws://${host}:${port}/ws` });
	}
};
