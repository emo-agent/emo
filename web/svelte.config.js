import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		adapter: adapter({
			// Output to web/build — consumed by PyInstaller and the daemon's static server
			pages: 'build',
			assets: 'build',
			fallback: 'index.html', // SPA fallback for client-side routing
			precompress: false
		})
	}
};

export default config;
