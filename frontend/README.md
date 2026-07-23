# DnD Notes frontend

This directory contains the Vue frontend for DnD Notes. It is developed with
Vite and compiled into static files that the FastAPI application serves in
production.

## Requirements

Use a Node.js version accepted by the `engines` field in `package.json`.

Install the locked dependencies from this directory:

```sh
npm ci
```

The project currently uses the beta Vue packages together with Vue Router,
TypeScript, Vite, and the Vue TypeScript checker. Refer to `package.json` for
the exact versions.

## Development

Start the FastAPI backend on `http://localhost:8000`, then run:

```sh
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`. Development API
requests are sent directly to `http://localhost:8000/api`, so the frontend is
not useful on its own without the backend.

## Commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the Vite development server. |
| `npm run type-check` | Check Vue and TypeScript files without emitting output. |
| `npm run build` | Compile the production frontend into `frontend/dist`. |
| `npm run preview` | Preview a previously compiled frontend. |

The repository build script runs the type-check and frontend build before
packaging the backend. See [BUILDING.md](../BUILDING.md) for the complete
production workflow.

## Source layout

- `src/views`: route-level campaign, resource, search, character, and inventory
  views
- `src/components`: reusable UI components
- `src/stores`: shared campaign and search state
- `src/types`: API and UI TypeScript types
- `src/composables`: reusable route and resource-selection behavior
- `src/apihelpers.js`: API requests, response normalization, and error handling
