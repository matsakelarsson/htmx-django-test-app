# htmx-django-test-app

A small Django 6 project wired up with [htmx](https://htmx.org) 2 and Tailwind CSS 4, built to try
out server-driven partial updates. The demo is a todo list with tags where every interaction is an
HTMX request that returns HTML fragments, including dragging a todo onto a tag and choosing a due
date from a server-rendered date picker.

There is no Node.js and no hand-written JavaScript. Tailwind is compiled by
[django-tailwind-cli](https://django-tailwind-cli.readthedocs.io/), which downloads the standalone
Tailwind binary into `.django_tailwind_cli/` on first use. The only script on the page is the htmx
library itself, served by Django from the copy bundled with django-htmx.

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
| Drop a todo on a tag | `hx-post`, `hx-trigger="drop"`, `hx-include="#dragged-todo"` | The tag card plus an out-of-band status message |
| Add with a tag's picker | plain form with `hx-post` to the same URL | Same as a drop |
| Remove a todo from a tag | `hx-delete`, `hx-swap="outerHTML"` | The tag card, with focus moved to its picker |
| Create a tag | `hx-post`, `hx-target="this"` | A fresh form plus the tag list out of band, or 422 with the error |
| Open the date picker | `popovertarget` plus `hx-get` on the same button | The month grid for whatever the input holds |
| Change month or year | `hx-get`, `hx-swap="innerHTML"` into the popover | The new month grid |
| Pick a day | `hx-get`, `hx-swap="outerHTML"` on the widget | The whole widget with the date filled in and the popover closed |

Other bits worth noticing:

- `templates/base.html` sets `hx-headers` on `<body>` so every HTMX request carries the CSRF token.
- `django-htmx` middleware exposes `request.htmx`; views fall back to redirects for non-HTMX requests.
- The form submits normally without JavaScript, so the page still works with htmx blocked.
- `hx-indicator` shows a "Saving…" hint while a request is in flight, using htmx's built-in indicator styles.
- Tailwind classes live in the templates and in `todos/forms.py` (the input widget). Tailwind 4 scans
  both automatically, so there is no content list to maintain.
- Dark mode follows the system preference via Tailwind's `dark:` variant.

## Drag and drop

Dragging a todo onto a tag adds it to `Tag.todos`, a `ManyToManyField`. It uses the browser's native
drag and drop, htmx attributes, and Tailwind variants. There is no JavaScript file and no library.

How it fits together:

1. **Source.** Each todo row has `draggable="true"`. Its `hx-on:dragstart` puts the id on the drag
   under a custom type, copies it into the hidden `#dragged-todo` input, and sets `data-dragging`
   on the row. `hx-on:dragend` removes the attribute again.
2. **Reveal.** Every tag card contains a drop overlay that is `hidden` by default. The Tailwind
   variant `group-has-data-dragging/board:flex` shows it while any row carries `data-dragging`.
3. **Target.** The overlay has `hx-post`, `hx-trigger="drop"` and `hx-include="#dragged-todo"`.
   Its `hx-on:dragenter` and `hx-on:dragover` cancel those events, which is what makes an element
   accept drops. They also toggle `data-over`, which Tailwind styles as the hover highlight.
4. **Server.** `tag_add_todo` validates the id with a `ModelChoiceField`, calls `tag.todos.add()`,
   and returns the re-rendered card plus a status message.

Why it is built this way:

- **Hidden input instead of reading the drag data in `hx-vals`.** The browser only lets a page read
  drag data during the `drop` event itself. htmx evaluates `hx-vals` later when a request is queued,
  and htmx 4 no longer passes the event to `hx-vals` at all. A hidden input has neither problem.
- **An overlay instead of the card as the target.** The overlay has no child nodes, so the browser
  fires `dragenter` and `dragleave` once each and the highlight cannot flicker. Its request
  attributes are also not inherited by the buttons inside the card.
- **`hx-on:drop` cancels the event.** htmx only cancels form submits and link clicks.
- **A busy target ignores the pointer.** While its request is in flight the overlay has
  `pointer-events: none`, so a second drop cannot be queued and silently lost.
- **A picker in every tag card.** WCAG 2.2 criterion 2.5.7 requires a way to do the same thing
  without dragging. The select and button post to the same URL, work from the keyboard, and work
  without JavaScript. They are also the fallback where touch dragging is missing, such as Firefox
  for Android and iPhones before iOS 15.
- **A persistent status region.** `#tag-status` has `role="status"` and stays in the page. Responses
  replace only its text with `hx-swap-oob="innerHTML"`, so screen readers announce the outcome.
- **422 for invalid requests.** The `htmx-config` meta tag in `base.html` lets htmx swap 422
  responses, so a drop of a todo that no longer exists shows a message instead of failing silently.

Verified with the Django test suite and with real mouse-driven drags in headless Brave
(Chromium 154). It has not been exercised in Firefox, Safari, or on a touch device.

If you upgrade to htmx 4, the drag-and-drop attributes need no changes. According to the htmx 4
upgrade notes, attribute inheritance becomes explicit, so the `hx-headers` on `<body>` that
carries the CSRF token will need the `:inherited` suffix.

## Date picker

`datepicker/` is a small reusable app: a form widget that pairs a text input with a calendar
popover. It uses only Django, htmx attributes and Tailwind classes. The templates contain no
script, no `hx-on` handler and no evaluated expression, and a test enforces that.

```python
from datepicker.widgets import DatePickerInput

class TodoForm(forms.ModelForm):
    class Meta:
        model = Todo
        fields = ["title", "due_date"]
        widgets = {"due_date": DatePickerInput()}
```

Include `datepicker.urls` under the `datepicker` namespace, as `config/urls.py` does.

How it fits together:

1. **Open.** The calendar button has `popovertarget`, so the browser's Popover API opens and closes
   the panel, including on Escape and on a click outside. The same click carries `hx-get`, which
   loads the month that matches whatever the input holds, typed or picked.
2. **Navigate.** The month and year arrows are `hx-get` buttons that swap the grid inside the
   open popover. Stable ids let htmx put focus back on the arrow that was pressed.
3. **Pick.** Each day is an `hx-get` button whose response is the whole widget with the date
   filled in. The new popover arrives closed, so swapping it in is what closes the calendar.
4. **Place.** CSS anchor positioning puts the popover under the input and flips it above when
   there is no room. Browsers without it show the popover centred instead.

Things worth knowing:

- **The input stays typable.** It accepts every format the form field accepts, and the calendar
  follows it. Typing is also the quick route for keyboard users, because the days are ordinary
  buttons reached with Tab rather than an arrow-key grid, which would need JavaScript.
- **State lives in ARIA attributes.** The selected day has `aria-pressed`, today has
  `aria-current="date"`, and Tailwind styles from those same attributes.
- **The widget isolates itself.** htmx 2 lets children inherit attributes such as `hx-swap` and
  `hx-indicator` from a surrounding form. The wrapper sets `hx-disinherit="*"` and every request
  element names its own target and swap, so the widget behaves the same wherever it is placed.
- **Locale aware.** The first day of the week and the month and weekday names follow Django's
  active locale.
- **"Today" is the server's date.** With `TIME_ZONE = "UTC"` it can differ from the visitor's
  date around midnight.
- **Use a `<label>` for the field.** A pick re-renders the widget from its field name and id
  alone, so extra attrs passed to the widget are not carried over.

Browser support, from MDN's compatibility data: the Popover API needs Chrome 114, Firefox 125 or
Safari 17. Anchor positioning needs Chrome 129, Firefox 147 or Safari 26. Verified with the Django
tests and with real clicks and key presses in headless Brave (Chromium 154). Not exercised in
Firefox or Safari.

## Layout

```
config/                 Django project (settings, root urls)
todos/                  App: models (Todo, Tag), forms, views, urls, tests
datepicker/             Reusable date picker: widget, views, urls, tests, and its own templates
templates/
  base.html             Page shell: Tailwind stylesheet, htmx script tag
  todos/
    index.html          Full page
    partials/           Fragments returned by HTMX views: _form, _list, _item, _status for todos,
                        and _tag_form, _tag_list, _tag, _tag_status for tags
assets/css/tailwind.css Built stylesheet (generated, ignored by git)
.django_tailwind_cli/   Tailwind binary and source.css (managed by django-tailwind-cli)
```
