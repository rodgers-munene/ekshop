"""Custom date ranges must be inclusive, bounded, and EAT-aligned."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.routers.admin import (
    MAX_CUSTOM_DAYS,
    _period_bounds,
    _resolve_window,
)

EAT = timezone(timedelta(hours=3))


class TestPresetsStillWork:
    @pytest.mark.parametrize("preset", ["today", "yesterday", "week", "month"])
    def test_preset_returns_a_window(self, preset):
        since, until, label = _resolve_window(preset, 30, None, None)
        assert since < until
        assert label == preset

    def test_no_arguments_falls_back_to_days(self):
        _, _, label = _resolve_window(None, 14, None, None)
        assert label == "days"


class TestCustomRange:
    def test_explicit_range_overrides_the_preset(self):
        """A saved link to a range must keep working even if presets change."""
        since, until, label = _resolve_window(
            "month", 30, date(2026, 9, 1), date(2026, 9, 30)
        )
        assert since.date() == date(2026, 9, 1)
        assert label == "2026-09-01 to 2026-09-30"
        assert until.date() == date(2026, 10, 1)

    def test_end_date_is_inclusive(self):
        """Asking for the 1st to the 3rd must include the whole of the 3rd, not
        stop at midnight on it -- otherwise the last day always looks empty."""
        since, until, _ = _resolve_window(None, 14, date(2026, 9, 1), date(2026, 9, 3))
        assert since.date() == date(2026, 9, 1)
        assert until.date() == date(2026, 9, 4)

    def test_bounds_are_eat_midnights(self):
        """Naive local midnights would be three hours off, quietly dropping or
        double counting orders either side of midnight."""
        since, until, _ = _resolve_window(None, 14, date(2026, 9, 1), date(2026, 9, 3))
        assert since.utcoffset() == timedelta(hours=3)
        assert until.utcoffset() == timedelta(hours=3)
        assert since.hour == 0 and since.minute == 0

    def test_single_day_range(self):
        since, until, _ = _resolve_window(None, 14, date(2026, 9, 1), date(2026, 9, 1))
        assert until - since == timedelta(days=1)

    def test_reversed_range_is_normalised(self):
        """Two dates typed in the wrong order should not return an empty window
        or a 422; they should just work."""
        since, until, _ = _resolve_window(None, 14, date(2026, 9, 10), date(2026, 9, 1))
        assert since.date() == date(2026, 9, 1)
        assert until.date() == date(2026, 9, 11)

    def test_only_a_start_date_uses_days_as_the_span(self):
        since, until, _ = _resolve_window(None, 7, date(2026, 9, 1), None)
        assert since.date() == date(2026, 9, 1)
        assert until.date() == date(2026, 9, 8)

    def test_only_an_end_date_works_too(self):
        since, until, _ = _resolve_window(None, 7, None, date(2026, 9, 7))
        assert since.date() == date(2026, 9, 1)
        assert until.date() == date(2026, 9, 8)


class TestBounds:
    def test_an_absurd_range_is_refused(self):
        """Unbounded ranges on an analytics endpoint are how one click becomes a
        scan of the whole order table."""
        with pytest.raises(HTTPException) as exc:
            _resolve_window(None, 14, date(2000, 1, 1), date(2026, 1, 1))
        assert exc.value.status_code == 422
        assert str(MAX_CUSTOM_DAYS) in str(exc.value.detail)

    def test_exactly_the_maximum_is_allowed(self):
        since, until, _ = _resolve_window(
            None, 14, date(2026, 1, 1), date(2026, 1, 1) + timedelta(days=MAX_CUSTOM_DAYS - 1)
        )
        assert until - since == timedelta(days=MAX_CUSTOM_DAYS)

    def test_one_day_over_the_maximum_is_refused(self):
        with pytest.raises(HTTPException):
            _resolve_window(
                None, 14, date(2026, 1, 1),
                date(2026, 1, 1) + timedelta(days=MAX_CUSTOM_DAYS),
            )


class TestYesterday:
    def test_yesterday_is_a_whole_calendar_day(self):
        """A complete day in EAT, so it lines up with a point on the trend rather
        than being a rolling 24 hours that straddles two dates."""
        since, until = _period_bounds("yesterday", 30)
        assert until - since == timedelta(days=1)
        assert since.hour == 0 and since.minute == 0
        assert until.hour == 0 and until.minute == 0
        assert until.date() == since.date() + timedelta(days=1)