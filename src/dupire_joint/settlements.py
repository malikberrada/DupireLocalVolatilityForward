"""Explicit index fixing conventions, with a bounded official calendar.

This is a scheduled fixing time, not the time cash reaches an account.
The bundled schedule is conditional on no exceptional market closure.
"""
from __future__ import annotations
import csv
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CALENDAR_SOURCE = "https://ir.theice.com/press/news-details/2025/NYSE-Group-Announces-2026-2027-and-2028-Holiday-and-Early-Closings-Calendar/"
CONTRACT_SOURCE = "https://cdn.cboe.com/resources/xsp/XSP_Options_Fact_Sheet.pdf"
CLOSED = {
    2026: "01-01 01-19 02-16 04-03 05-25 06-19 07-03 09-07 11-26 12-25",
    2027: "01-01 01-18 02-15 03-26 05-31 06-18 07-05 09-06 11-25 12-24",
    2028: "01-17 02-21 04-14 05-29 06-19 07-04 09-04 11-23 12-25",
}
EARLY = {"2026-11-27", "2026-12-24", "2027-11-26", "2028-07-03", "2028-11-24"}
ROOTS = {("^SPX", "SPX"): "AM", ("^SPX", "SPXW"): "PM", ("^XSP", "XSP"): "PM"}


def aware_utc(value):
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("An explicit UTC offset is required for every timestamp")
    return d.astimezone(timezone.utc)


def load_overrides(path):
    if not path:
        return {}
    result = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row["symbol"], row["root"], row["expiry"])
            if key in result or key[:2] not in ROOTS:
                raise ValueError("Duplicate or unsupported settlement override")
            if row.get("settlement") != ROOTS[key[:2]] or not row.get("source"):
                raise ValueError("Override needs the expected AM/PM convention and its source")
            result[key] = {"fixing_utc": aware_utc(row["fixing_utc"]).isoformat(),
                           "settlement": row["settlement"], "source": row["source"],
                           "calendar": "explicit_override", "assumption": "user_supplied_fixing"}
    return result


def scheduled_fixing(symbol, root, expiry, overrides=None):
    key = (symbol, root, expiry)
    if key[:2] not in ROOTS:
        raise ValueError("Supported symbol/root combinations are ^SPX/SPX, ^SPX/SPXW, ^XSP/XSP")
    if key in (overrides or {}):
        return dict(overrides[key])
    d = date.fromisoformat(expiry)
    if d.year not in CLOSED:
        raise ValueError("Bundled calendar covers 2026-2028; provide --settlements for other dates")
    if d.weekday() >= 5 or d.strftime("%m-%d") in CLOSED[d.year].split():
        raise ValueError("Expiry is not an equity session; provide an explicit verified fixing override")
    try:
        ny = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError as exc:
        raise ValueError("New York timezone unavailable: python -m pip install tzdata") from exc
    label = ROOTS[key[:2]]
    hh, mm = (9, 30) if label == "AM" else (13 if expiry in EARLY else 16, 0)
    fixing = datetime.combine(d, time(hh, mm), ny).astimezone(timezone.utc)
    return {"fixing_utc": fixing.isoformat(), "settlement": label,
            "source": CONTRACT_SOURCE, "calendar_source": CALENDAR_SOURCE,
            "calendar": "scheduled_NYSE_2026_2028", "early_close": expiry in EARLY,
            "assumption": "scheduled_open_reference_not_actual_SET_publication" if label == "AM"
                          else "scheduled_underlying_equity_close_no_exceptional_closure"}
