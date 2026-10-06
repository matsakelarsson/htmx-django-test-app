import re
from calendar import Calendar
from datetime import date, timedelta
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import BadRequest, ValidationError
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dates import WEEKDAYS, WEEKDAYS_ABBR
from django.utils.formats import get_format
from django.views.decorators.http import require_GET

from .widgets import DatePickerInput

# Field names and element ids are echoed into HTML and CSS, so accept only plain identifiers.
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
ISO_MONTH = re.compile(r"(\d{4})-(\d{2})\Z")
FIRST_MONTH, LAST_MONTH = date(1900, 1, 1), date(2199, 12, 1)


def picker_identity(request):
    """The field name, element id and required flag that tie a request to one widget."""
    identity = {"dp_field": request.GET.get("dp_field", ""), "dp_id": request.GET.get("dp_id", "")}
    if not all(IDENTIFIER.match(value) for value in identity.values()):
        raise BadRequest("Invalid date picker identifiers.")
    if request.GET.get("dp_required"):
        identity["dp_required"] = "1"
    return identity


def parse_typed_date(value):
    """Read a date the way a DateField would, so the calendar follows what the user typed."""
    try:
        return forms.DateField(required=False).to_python(value)
    except ValidationError:
        return None


def parse_iso_date(value):
    if not ISO_DATE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_month(value):
    match = ISO_MONTH.match(value)
    if not match or not 1 <= int(match[2]) <= 12 or not FIRST_MONTH.year <= int(match[1]) <= LAST_MONTH.year:
        return None
    return date(int(match[1]), int(match[2]), 1)


def shift(month, months):
    index = month.year * 12 + month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def build_calendar(identity, month, selected, today, *, focus):
    """Template context for one month: a six-week grid plus the links to move and to pick."""

    def calendar_url(target):
        if not FIRST_MONTH <= target <= LAST_MONTH:
            return None
        params = {
            **identity,
            "dp_month": f"{target:%Y-%m}",
            "dp_selected": selected.isoformat() if selected else "",
        }
        return f"{reverse('datepicker:calendar')}?{urlencode(params)}"

    def pick_url(day):
        params = {**identity, "dp_date": day.isoformat() if day else ""}
        return f"{reverse('datepicker:pick')}?{urlencode(params)}"

    def nav(key, label, symbol, months):
        target = shift(month, months)
        return {"key": key, "label": label, "symbol": symbol, "target": target, "url": calendar_url(target)}

    def in_month(day):
        return day is not None and (day.year, day.month) == (month.year, month.month)

    # Django numbers weekdays from Sunday, Python's calendar from Monday.
    grid = Calendar(firstweekday=(get_format("FIRST_DAY_OF_WEEK") - 1) % 7)
    weeks = grid.monthdatescalendar(month.year, month.month)
    while len(weeks) < 6:  # same height for every month, so the popover never jumps
        start = weeks[-1][-1] + timedelta(days=1)
        weeks.append([start + timedelta(days=offset) for offset in range(7)])

    # On opening, put keyboard focus on the most useful day.
    focus_day = next(day for day in (selected, today, month) if in_month(day)) if focus else None

    return {
        "id": identity["dp_id"],
        "month": month,
        "weekdays": [
            {"name": WEEKDAYS[number], "abbr": str(WEEKDAYS_ABBR[number])[:2]} for number in grid.iterweekdays()
        ],
        "weeks": [
            [
                {
                    "date": day,
                    "outside": not in_month(day),
                    "selected": day == selected,
                    "today": day == today,
                    "focus": day == focus_day,
                    "pick_url": pick_url(day),
                }
                for day in week
            ]
            for week in weeks
        ],
        "nav_before": [nav("prev-year", "Previous year", "«", -12), nav("prev-month", "Previous month", "‹", -1)],
        "nav_after": [nav("next-month", "Next month", "›", 1), nav("next-year", "Next year", "»", 12)],
        "today_url": pick_url(today),
        "clear_url": pick_url(None),
    }


@require_GET
def calendar(request):
    """The month grid, loaded into the popover when it opens and when the month changes."""
    identity = picker_identity(request)
    today = timezone.localdate()
    if "dp_month" in request.GET:  # moving between months
        month = parse_month(request.GET["dp_month"])
        if month is None:
            raise BadRequest("Invalid month.")
        selected = parse_iso_date(request.GET.get("dp_selected", ""))
        focus = False  # keep focus on the navigation button that was pressed
    else:  # opening: follow whatever the input holds right now
        selected = parse_typed_date(request.GET.get(identity["dp_field"], ""))
        month = (selected or today).replace(day=1)
        if not FIRST_MONTH <= month <= LAST_MONTH:
            month = today.replace(day=1)
        focus = True
    context = build_calendar(identity, month, selected, today, focus=focus)
    return render(request, "datepicker/calendar.html", context)


@require_GET
def pick(request):
    """The whole widget with a new value. Its popover is rendered closed, which closes the calendar."""
    identity = picker_identity(request)
    raw = request.GET.get("dp_date", "")
    value = parse_iso_date(raw)
    if raw and value is None:
        raise BadRequest("Invalid date.")
    attrs = {"id": identity["dp_id"]}
    if "dp_required" in identity:
        attrs["required"] = True
    widget = DatePickerInput(focus_toggle=True)
    return HttpResponse(widget.render(identity["dp_field"], value, attrs))
