# babusovereign.github.io

Personal site of Babu Sovereign Perumalla, served by GitHub Pages at
[babusovereign.com](https://babusovereign.com/) (custom domain via `CNAME`).

## Pages

- `/` (`index.html`): home, with the animated San Francisco sky hero (air show, night traffic, bridges, skyline).
- `/builds/` (`builds/index.html`): Builds.
- `/ledger/` (`ledger/index.html`): The ledger.

Each page is one hand-written HTML file with its CSS and page-specific JS inline.

## Shared assets

- `assets/theme.js`: the light/dark toggle button logic, shared by all three pages.
- `assets/q5-day.webp`, `assets/q5-night.webp`: the nav-bar car (red Audi Q5 by day, white by night).

## Day/night theme

- `data-theme="light|dark"` on `<html>` picks the theme. If it isn't set, the OS `prefers-color-scheme` decides.
- The user's choice is saved in `localStorage` under the key `theme`.
- A small inline script in each page's `<head>` applies the saved theme before first paint. It also re-applies it when the page comes back from the back/forward cache and when another tab changes it.
- Every dark style is written twice: once as `:root[data-theme="dark"] …` and once as `@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) …}`.

## Build / deploy

There is no build step. Edit the HTML and push to `main`, and GitHub Pages serves it as-is.

`.github/workflows/skywatch-snapshot.yml` is a separate job that publishes flight-data snapshots to the `skywatch-data` branch.
