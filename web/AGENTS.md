# web/AGENTS.md

## Stack

- **SvelteKit** + **Svelte 5**, TypeScript
- **Package manager**: pnpm (never npm or yarn)
- **CSS**: Tailwind v4 via `@tailwindcss/vite` — no `tailwind.config.js`, config lives in CSS
- **UI components**: shadcn-svelte (nova style, mist base color, lucide icons)
- **AI UI elements**: svelte-ai-elements
- **Icons**: `@lucide/svelte`

## Commands

```bash
pnpm dev          # dev server
pnpm build        # production build
pnpm preview      # preview production build
pnpm check        # svelte-check (type errors)
pnpm lint         # prettier + eslint
pnpm format       # prettier write
```

## Runes mode

Runes mode is **forced project-wide** in `svelte.config.js`:
```js
runes: ({ filename }) => filename.split(/[/\\]/).includes('node_modules') ? undefined : true
```
Always use Svelte 5 runes syntax (`$state`, `$derived`, `$effect`, `$props`, etc.) — never legacy `$:`, `export let`, or `createEventDispatcher`.

## Adding UI components

shadcn-svelte is the source for all base UI components:
```bash
pnpm dlx shadcn-svelte@latest add <component>
# e.g. pnpm dlx shadcn-svelte@latest add button dialog
```
Components land in `src/lib/components/ui/`. Use the shadcn MCP server when available to find component names and APIs.

## AI UI elements

Use **svelte-ai-elements** for AI-specific UI (streaming text, chat bubbles, etc.).  
Docs: https://svelte-ai-elements.vercel.app/docs/installation

## Path aliases

| Alias | Resolves to |
|---|---|
| `$lib` | `src/lib` |
| `$lib/components` | `src/lib/components` |
| `$lib/components/ui` | shadcn components |
| `$lib/hooks` | `src/lib/hooks` |
| `$lib/utils` | `src/lib/utils.ts` |

## Global CSS

`src/routes/layout.css` — Tailwind base, CSS variables for theming. Import additional styles here, not in `vite.config.ts`.

## Svelte MCP server

Active via `.opencode/opencode.json`. Use it for Svelte 5 and SvelteKit documentation:

1. **`list-sections`** — call first to find relevant docs sections
2. **`get-documentation`** — fetch all relevant sections identified above
3. **`svelte-autofixer`** — run on any Svelte code before finalising; repeat until no issues
4. **`playground-link`** — only on user request, never when code was written to files

## Project configuration

- `components.json` — shadcn-svelte config (style: nova, baseColor: mist, iconLibrary: lucide)
- `svelte.config.js` — adapter-auto, runes forced
- `vite.config.ts` — only `tailwindcss()` and `sveltekit()` plugins
- `tsconfig.json` — strict mode, moduleResolution: bundler
