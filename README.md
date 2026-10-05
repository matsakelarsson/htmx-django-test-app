# htmx-django-test-app

A small Django 6 project wired up with [htmx](https://htmx.org) 2 and Tailwind CSS 4, built to try
out server-driven partial updates. The demo is a todo list where every interaction is an HTMX
request that returns HTML fragments.

There is no Node.js and no hand-written JavaScript. Tailwind is compiled by
[django-tailwind-cli](https://django-tailwind-cli.readthedocs.io/), which downloads the standalone
Tailwind binary into `.django_tailwind_cli/` on first use. The only script on the page is the htmx
library itself, loaded from a CDN.

## Run it

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py tailwind runserver
```

`tailwind runserver` starts the Django dev server and a Tailwind watcher that rebuilds
`assets/css/tailwind.css` whenever a template changes. Open http://127.0.0.1:8000/.

Other useful commands:

```sh
uv run python manage.py tailwind build     # one-off minified CSS build
uv run python manage.py tailwind watch     # watcher only
uv run python manage.py test
uv run python manage.py createsuperuser    # then browse /admin/
```

## What the demo shows

| Interaction | HTMX attributes | Server returns |
| --- | --- | --- |
| Add a todo | `hx-post`, `hx-target="#todo-list"`, `hx-swap="beforeend"` | New `<li>`, plus out-of-band swaps for the status line and a fresh form |
| Blank title | same form | Only the form, re-rendered with the validation error (out of band) |
| Toggle done | `hx-post` on the checkbox, `hx-swap="outerHTML"` | The updated `<li>` plus an out-of-band status line |
| Delete | `hx-delete`, `hx-swap="delete"` | Only the out-of-band status line |
| Clear completed | `hx-post`, `hx-target="#todo-list"`, `hx-swap="outerHTML"` | The whole list plus the status line |

Other bits worth noticing:

- `templates/base.html` sets `hx-headers` on `<body>` so every HTMX request carries the CSRF token.
- `django-htmx` middleware exposes `request.htmx`; views fall back to redirects for non-HTMX requests.
- The form submits normally without JavaScript, so the page still works with htmx blocked.
- `hx-indicator` shows a "Saving…" hint while a request is in flight, using htmx's built-in indicator styles.
- Tailwind classes live in the templates and in `todos/forms.py` (the input widget). Tailwind 4 scans
  both automatically, so there is no content list to maintain.
- Dark mode follows the system preference via Tailwind's `dark:` variant.

## Layout

```
config/                 Django project (settings, root urls)
todos/                  App: model, form, views, urls, tests
templates/
  base.html             Page shell: Tailwind stylesheet, htmx script tag
  todos/
    index.html          Full page
    partials/           Fragments returned by HTMX views (_form, _list, _item, _status)
assets/css/tailwind.css Built stylesheet (generated, ignored by git)
.django_tailwind_cli/   Tailwind binary and source.css (managed by django-tailwind-cli)
```
