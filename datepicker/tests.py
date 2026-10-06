import re
from datetime import date
from unittest import mock

from django import forms
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from .views import shift
from .widgets import DatePickerInput

TODAY = date(2026, 10, 5)  # a Monday
IDENTITY = {"dp_field": "due_date", "dp_id": "id_due_date"}


def assert_requests_are_explicit(test, html, *, expected):
    """Every element that issues a request must name its own target and swap."""
    tags = [tag for tag in re.findall(r"<[a-z]+\b[^>]*>", html) if "hx-get=" in tag]
    test.assertEqual(len(tags), expected)
    for tag in tags:
        test.assertIn("hx-target=", tag)
        test.assertIn("hx-swap=", tag)


class WidgetTests(SimpleTestCase):
    def render(self, value=None, attrs=None):
        return DatePickerInput().render("due_date", value, attrs if attrs is not None else {"id": "id_due_date"})

    def test_renders_input_toggle_and_closed_popover(self):
        html = self.render(date(2026, 10, 15))
        self.assertIn('<input type="text" name="due_date" value="2026-10-15"', html)
        self.assertIn('id="id_due_date"', html)
        self.assertIn('placeholder="YYYY-MM-DD"', html)
        # The button opens the popover natively and has htmx load the calendar for the typed value.
        self.assertIn('popovertarget="id_due_date-calendar"', html)
        self.assertIn('hx-get="/datepicker/calendar/?dp_field=due_date&amp;dp_id=id_due_date"', html)
        self.assertIn('hx-include="#id_due_date"', html)
        self.assertIn('hx-target="#id_due_date-calendar" hx-swap="innerHTML"', html)
        self.assertIn('<div popover id="id_due_date-calendar"', html)
        # Anchor names tie this popover to this wrapper, so several pickers can share a page.
        self.assertIn('style="anchor-name: --dp-id_due_date"', html)
        self.assertIn('style="position-anchor: --dp-id_due_date"', html)
        self.assertNotIn("autofocus", html)

    def test_empty_value_renders_no_value_attribute(self):
        self.assertNotIn("value=", self.render(None))

    def test_unparsable_text_is_shown_back(self):
        self.assertIn('value="next friday"', self.render("next friday"))

    def test_id_defaults_when_none_is_given(self):
        html = self.render(attrs={})
        self.assertIn('id="id_due_date"', html)
        self.assertIn('id="id_due_date-picker"', html)

    def test_required_field_tells_the_views(self):
        class Form(forms.Form):
            when = forms.DateField(widget=DatePickerInput())

        html = str(Form()["when"])
        self.assertIn(" required", html)
        self.assertIn("dp_field=when&amp;dp_id=id_when&amp;dp_required=1", html)

    def test_widget_is_isolated_from_surrounding_htmx_attributes(self):
        # A form around the widget may set hx-swap, hx-target or hx-indicator for itself.
        html = self.render()
        self.assertIn('hx-disinherit="*"', html)
        assert_requests_are_explicit(self, html, expected=1)

    def test_widget_ships_no_javascript(self):
        html = self.render(date(2026, 10, 15))
        for needle in ("<script", "hx-on", "js:", "javascript:", "onclick"):
            self.assertNotIn(needle, html)


@mock.patch("datepicker.views.timezone.localdate", return_value=TODAY)
class CalendarViewTests(SimpleTestCase):
    def get(self, **params):
        return self.client.get(reverse("datepicker:calendar"), {**IDENTITY, **params})

    def test_opening_shows_current_month_and_focuses_today(self, _):
        response = self.get()
        self.assertContains(response, "October 2026</h2>")
        self.assertContains(response, 'aria-label="Monday 5 October 2026" aria-current="date" autofocus')
        self.assertNotContains(response, 'aria-pressed="true"')

    def test_opening_follows_the_typed_value(self, _):
        response = self.get(due_date="2027-02-14")
        self.assertContains(response, "February 2027</h2>")
        self.assertContains(response, 'aria-label="Sunday 14 February 2027" aria-pressed="true" autofocus')

    def test_opening_accepts_every_format_the_form_field_accepts(self, _):
        response = self.get(due_date="02/14/2027")
        self.assertContains(response, "February 2027</h2>")
        self.assertContains(response, 'aria-label="Sunday 14 February 2027" aria-pressed="true"')

    def test_opening_with_unparsable_text_falls_back_to_today(self, _):
        response = self.get(due_date="soon")
        self.assertContains(response, "October 2026</h2>")
        self.assertNotContains(response, 'aria-pressed="true"')

    def test_grid_is_always_six_weeks(self, _):
        # February 2026 fits in exactly four Sunday-first weeks; it is still padded to six.
        for month in ("2026-02", "2026-10", "2026-08"):
            with self.subTest(month=month):
                self.assertContains(self.get(dp_month=month), "<td", count=42)

    def test_week_starts_on_the_locale_first_day(self, _):
        content = self.get().content.decode()
        self.assertLess(content.index('title="Sunday"'), content.index('title="Monday"'))
        with override_settings(LANGUAGE_CODE="en-gb"):
            content = self.get().content.decode()
        self.assertLess(content.index('title="Monday"'), content.index('title="Sunday"'))

    def test_navigation_moves_month_and_keeps_selection(self, _):
        response = self.get(dp_month="2026-12", dp_selected="2026-10-15")
        self.assertContains(response, "December 2026</h2>")
        self.assertContains(response, "dp_month=2027-01&amp;dp_selected=2026-10-15")  # next month
        self.assertContains(response, "dp_month=2026-11&amp;dp_selected=2026-10-15")  # previous month
        self.assertContains(response, "dp_month=2025-12&amp;dp_selected=2026-10-15")  # previous year
        self.assertContains(response, "dp_month=2027-12&amp;dp_selected=2026-10-15")  # next year
        self.assertContains(response, 'aria-label="Next month, January 2027"')
        # Focus must stay on the navigation button, so nothing asks for it.
        self.assertNotContains(response, "autofocus")

    def test_selected_day_is_marked_even_when_it_belongs_to_the_next_month(self, _):
        response = self.get(dp_month="2026-09", dp_selected="2026-10-01")
        self.assertContains(response, 'aria-label="Thursday 1 October 2026" aria-pressed="true" tabindex="-1"')

    def test_days_outside_the_month_are_muted_and_skipped_by_tab(self, _):
        response = self.get(dp_month="2026-09")
        self.assertContains(response, 'aria-label="Thursday 1 October 2026" tabindex="-1" data-outside')

    def test_every_day_links_to_pick_and_targets_the_widget(self, _):
        response = self.get()
        self.assertContains(response, "/datepicker/pick/?dp_field=due_date&amp;dp_id=id_due_date&amp;dp_date=2026-10-15")
        self.assertContains(response, 'hx-target="#id_due_date-picker" hx-swap="outerHTML"', count=44)  # 42 days, Today, Clear
        self.assertContains(response, 'dp_date=2026-10-05" hx-target="#id_due_date-picker" hx-swap="outerHTML"\n            class="rounded-lg px-2 py-1 text-sm font-medium')  # Today
        self.assertContains(response, 'dp_date=" hx-target')  # Clear

    def test_bounds(self, _):
        # Count the attribute only; "disabled:" also appears in every button's class list.
        def disabled_buttons(month):
            return re.findall(r'id="id_due_date-([a-z-]+)"\s+aria-label="[^"]*"\s+disabled\s', self.get(dp_month=month).content.decode())

        self.assertEqual(disabled_buttons("1900-01"), ["prev-year", "prev-month"])
        self.assertEqual(disabled_buttons("2199-12"), ["next-month", "next-year"])
        self.assertEqual(disabled_buttons("2026-10"), [])
        self.assertEqual(disabled_buttons("1900-06"), ["prev-year"])
        for month in ("1899-12", "2200-01", "2026-13", "2026-00", "2026-1", "abc", ""):
            with self.subTest(month=month):
                self.assertEqual(self.get(dp_month=month).status_code, 400)

    def test_rejects_identifiers_that_are_not_plain_names(self, _):
        url = reverse("datepicker:calendar")
        for params in (
            {"dp_field": "due_date", "dp_id": "x;color:red"},
            {"dp_field": 'a"><b', "dp_id": "id_due_date"},
            {"dp_field": "due_date"},
            {},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(url, params).status_code, 400)

    def test_required_flag_is_carried_through(self, _):
        response = self.get(dp_required="1")
        self.assertContains(response, "dp_id=id_due_date&amp;dp_required=1&amp;dp_date=2026-10-15")

    def test_only_get_is_allowed(self, _):
        self.assertEqual(self.client.post(reverse("datepicker:calendar"), IDENTITY).status_code, 405)

    def test_every_calendar_request_names_its_target_and_swap(self, _):
        # 4 navigation buttons, 42 days, Today and Clear.
        assert_requests_are_explicit(self, self.get().content.decode(), expected=48)

    def test_calendar_ships_no_javascript(self, _):
        content = self.get().content.decode()
        for needle in ("<script", "hx-on", "js:", "javascript:", "onclick", "{%", "{#"):
            self.assertNotIn(needle, content)


class PickViewTests(SimpleTestCase):
    def get(self, **params):
        return self.client.get(reverse("datepicker:pick"), {**IDENTITY, **params})

    def test_returns_the_widget_with_the_date_and_focus_on_the_toggle(self):
        response = self.get(dp_date="2026-10-15")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_due_date-picker"')
        self.assertContains(response, '<input type="text" name="due_date" value="2026-10-15"')
        self.assertContains(response, 'aria-label="Choose date" autofocus')
        self.assertContains(response, "Loading calendar")  # popover comes back closed and empty

    def test_empty_date_clears_the_field(self):
        response = self.get(dp_date="")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "value=")

    def test_required_survives_the_round_trip(self):
        self.assertContains(self.get(dp_date="2026-10-15", dp_required="1"), " required")
        self.assertNotContains(self.get(dp_date="2026-10-15"), " required")

    def test_rejects_dates_that_are_not_real_iso_dates(self):
        for value in ("2026-02-30", "15/10/2026", "2026-10-5", "abc", "20261015"):
            with self.subTest(value=value):
                self.assertEqual(self.get(dp_date=value).status_code, 400)

    def test_rejects_bad_identifiers(self):
        response = self.client.get(reverse("datepicker:pick"), {"dp_field": "due_date", "dp_id": "a b", "dp_date": ""})
        self.assertEqual(response.status_code, 400)


class ShiftTests(SimpleTestCase):
    def test_crosses_year_boundaries(self):
        self.assertEqual(shift(date(2026, 1, 1), -1), date(2025, 12, 1))
        self.assertEqual(shift(date(2026, 12, 1), 1), date(2027, 1, 1))
        self.assertEqual(shift(date(2026, 5, 1), 12), date(2027, 5, 1))
        self.assertEqual(shift(date(2026, 5, 1), -12), date(2025, 5, 1))
