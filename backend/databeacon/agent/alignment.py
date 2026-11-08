"""Task specification and task-alignment verification.

The *task spec* fixes what the user asked for: the metric, the time periods (resolved
deterministically from data coverage), the grouping and the kind of comparison. After synthesis the
alignment check verifies, independently of the numeric evidence check, that

  * the answer's periods are the requested periods, the evidence it cites actually queried those
    periods, and the text does not talk about other periods;
  * the answer uses the requested metric and grouping, and so does the cited evidence;
  * the primary conclusion (e.g. "Enterprise contributed most") is what the cited evidence shows.

Numerically correct work on the wrong period, metric or grouping is therefore reported as
misaligned instead of successful.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

from .temporal import MONTHS, TemporalResolution

CHANGE_DIRECTIONS = {"largest_decline", "largest_increase"}
HIGH = {"highest", "largest_increase", "most", "max"}
LOW = {"lowest", "largest_decline", "least", "min"}


@dataclass
class TaskSpec:
    question: str
    question_type: str = "other"
    metric_column: str | None = None
    aggregation: str | None = None
    group_by: list[str] = field(default_factory=list)
    answer_target: str = ""
    date_column: str | None = None
    current: dict[str, Any] | None = None  # {"start","end","label",...}
    previous: dict[str, Any] | None = None
    comparison: str | None = None
    time_grain: str | None = None  # granularity the question asks for: day/week/month/quarter/year
    assumptions: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def grain(self) -> str | None:
        """Requested granularity (specs saved before this field existed are re-derived)."""
        return self.time_grain or requested_grain(self.question)

    def window(self) -> tuple[date, date] | None:
        if not self.current:
            return None
        start = date.fromisoformat((self.previous or self.current)["start"])
        return start, date.fromisoformat(self.current["end"])

    def prompt_block(self) -> str:
        lines = ["Task contract (use exactly this scope):"]
        if self.metric_column:
            lines.append(f"- metric: {self.aggregation or 'sum'}({self.metric_column})")
        if self.group_by:
            lines.append(f"- grouping: {', '.join(self.group_by)}")
        if self.current:
            lines.append(f"- current period: {self.current['label']} = [{self.current['start']}, {self.current['end']}) "
                         f"on {self.date_column}")
        if self.previous:
            lines.append(f"- comparison period: {self.previous['label']} = [{self.previous['start']}, "
                         f"{self.previous['end']})")
        if self.answer_target:
            lines.append(f"- answer: {self.answer_target}")
        for a in self.assumptions:
            lines.append(f"- assumption: {a}")
        return "\n".join(lines)


def build_spec(question: str, plan: dict[str, Any], temporal: TemporalResolution | None,
               columns: list[str]) -> TaskSpec:
    cols = {c.lower(): c for c in columns}
    spec = TaskSpec(question=question, question_type=plan.get("question_type") or "other",
                    aggregation=plan.get("aggregation") or None, answer_target=plan.get("answer_target") or "",
                    time_grain=requested_grain(question))
    metric = (plan.get("metric_column") or "").strip().strip('"')
    if metric:
        if metric.lower() in cols:
            spec.metric_column = cols[metric.lower()]
        else:
            spec.issues.append(f"plan metric '{metric}' is not a column; metric left unconstrained")
    for g in plan.get("group_by") or []:
        g = str(g).strip().strip('"')
        if g.lower() in cols:
            spec.group_by.append(cols[g.lower()])
        else:
            spec.issues.append(f"plan grouping '{g}' is not a column; ignored")
    if temporal and temporal.status == "resolved" and temporal.current:
        spec.date_column = temporal.column
        spec.current = temporal.current.to_dict()
        spec.previous = temporal.previous.to_dict() if temporal.previous else None
        spec.comparison = temporal.comparison
        spec.assumptions = list(temporal.assumptions)
    return spec


# --------------------------------------------------------------------------- helpers
_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_QLABEL_RE = re.compile(r"\b(?:Q([1-4])\s*((?:19|20)\d{2})|((?:19|20)\d{2})\s*[- ]?Q([1-4]))\b", re.I)
_MLABEL_RE = re.compile(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?\s+((?:19|20)\d{2})\b", re.I)


def _dates_in(obj: Any) -> list[date]:
    text = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    out = []
    for y, m, d in _ISO_RE.findall(text):
        try:
            out.append(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    return out


def _mentioned_periods(text: str) -> list[tuple[str, date, date]]:
    out = []
    for m in _QLABEL_RE.finditer(text):
        q, y = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        s = date(int(y), 3 * (int(q) - 1) + 1, 1)
        e = date(s.year + (s.month + 2) // 12, (s.month + 2) % 12 + 1, 1)
        out.append((m.group(0), s, e))
    for m in _MLABEL_RE.finditer(text):
        s = date(int(m.group(2)), MONTHS[m.group(1).lower()], 1)
        e = date(s.year + s.month // 12, s.month % 12 + 1, 1)
        out.append((m.group(0), s, e))
    return out


def _norm(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v)).strip().strip("'\"").lower()


# ---- time granularity
GRAINS = ("day", "week", "month", "quarter", "year")
_ADJ = {"day": "daily", "week": "weekly", "month": "monthly", "quarter": "quarterly", "year": "yearly"}
_GRAIN_WORDS = {
    "day": r"daily|per day|by day|each day|every day|day[- ]by[- ]day|day[- ]over[- ]day|which (?:day|date)|what (?:day|date)",
    "week": r"weekly|per week|by week|each week|every week|week[- ]by[- ]week|week[- ]over[- ]week|which week|what week",
    "month": r"monthly|per month|by month|each month|every month|month[- ]by[- ]month|month[- ]over[- ]month|"
             r"which month|what month",
    "quarter": r"quarterly|per quarter|by quarter|each quarter|quarter[- ]over[- ]quarter|which quarter|what quarter",
    "year": r"yearly|annual(?:ly)?|per year|by year|each year|year[- ]over[- ]year|which year|what year",
}
_GRAIN_ALIASES = {"d": "day", "day": "day", "days": "day", "date": "day", "w": "week", "week": "week",
                  "weeks": "week", "isoweek": "week", "m": "month", "ms": "month", "mon": "month", "month": "month",
                  "months": "month", "q": "quarter", "qs": "quarter", "quarter": "quarter", "quarters": "quarter",
                  "y": "year", "ys": "year", "a": "year", "year": "year", "years": "year"}


def requested_grain(question: str) -> str | None:
    """The time granularity the question explicitly asks for, or None when it does not say.
    Several different grains (e.g. "monthly ... per day") are ambiguous and give None."""
    q = (question or "").lower()
    found = [g for g, pat in _GRAIN_WORDS.items() if re.search(rf"\b(?:{pat})\b", q)]
    return found[0] if len(found) == 1 else None


def _grain_name(v: Any) -> str | None:
    return _GRAIN_ALIASES.get(str(v or "").strip().strip("'\"").lower())


_IDENT = r'"?([A-Za-z_][\w]*)"?'
_TRUNC_RE = re.compile(rf"date_trunc\s*\(\s*'(\w+)'\s*,\s*{_IDENT}\s*\)(?:\s*::\s*\w+)?\s+as\s+{_IDENT}", re.I)
_STRF_RE = re.compile(rf"strftime\s*\(\s*{_IDENT}\s*,\s*'([^']+)'\s*\)\s+as\s+{_IDENT}", re.I)
_CAST_RE = re.compile(rf"(?:cast\s*\(\s*{_IDENT}\s+as\s+date\s*\)|{_IDENT}\s*::\s*date)\s+as\s+{_IDENT}", re.I)
_STRF_GRAINS = {"%Y-%m-%d": "day", "%Y-%m": "month", "%Y": "year", "%Y-W%W": "week", "%Y-W%V": "week",
                "%G-W%V": "week", "%Y-%W": "week"}


def derived_time_groupings(evidence: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """Output columns that are a time bucket of a date column: {alias: (grain, source column)}, all
    lower-case. Read from the SQL (DATE_TRUNC/strftime/CAST AS DATE ... AS alias) and from time-series
    tool arguments (time_column + freq). Month-of-year style extractions (EXTRACT, date_part) are
    deliberately not included: they are not a timeline."""
    out: dict[str, tuple[str, str]] = {}
    for e in evidence:
        sql = e.get("sql") or (e.get("args") or {}).get("sql") or ""
        for unit, col, alias in _TRUNC_RE.findall(sql):
            if (g := _grain_name(unit)):
                out[alias.lower()] = (g, col.lower())
        for col, fmt, alias in _STRF_RE.findall(sql):
            if (g := _STRF_GRAINS.get(fmt)):
                out[alias.lower()] = (g, col.lower())
        for c1, c2, alias in _CAST_RE.findall(sql):
            out[alias.lower()] = ("day", (c1 or c2).lower())
        args = e.get("args") or {}
        if args.get("time_column") and (g := _grain_name(args.get("freq"))):
            col = str(args["time_column"]).lower()
            for alias in (g, "period", f"{col}_{g}", f"{g}_{col}"):
                out.setdefault(alias, (g, col))
    return out


# ---- dates in entities and text
_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
_DATE_PATTERNS = [
    # 2025-10-01, 2025/10/01
    (re.compile(r"\b((?:19|20)\d{2})[-/](\d{1,2})[-/](\d{1,2})\b"), "ymd"),
    # 2025-10, 2025/10 (not followed by another -dd)
    (re.compile(r"\b((?:19|20)\d{2})[-/](\d{1,2})\b(?![-/]\d)"), "ym"),
    # October 1, 2025 / Oct 1st 2025
    (re.compile(rf"\b({_MONTH_NAMES})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{{2}})\b", re.I), "mdy"),
    # 1 October 2025 / 1st of October 2025
    (re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_NAMES})\.?,?\s+((?:19|20)\d{{2}})\b", re.I), "dmy"),
    # October 2025 / Oct. 2025 / October of 2025
    (re.compile(rf"\b({_MONTH_NAMES})\.?,?\s+(?:of\s+)?((?:19|20)\d{{2}})\b", re.I), "my"),
]


def date_refs(text: Any) -> list[tuple[int, int, int | None]]:
    """Calendar dates written in ``text`` as (year, month, day or None). Covers ISO dates and months
    and written-out forms ("October 2025", "Oct 1, 2025", "1 October 2025"). Impossible dates
    (month 13, 31 June) are ignored rather than guessed."""
    s = str(text or "")
    out, taken = [], []
    for pat, kind in _DATE_PATTERNS:
        for m in pat.finditer(s):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue  # already read as part of a more specific form
            g = m.groups()
            if any(t == "may" for t in g if isinstance(t, str)):
                continue  # lower-case "may" is the verb ("we may 2025..."); the month is written "May"
            if kind == "ymd":
                y, mo, d = int(g[0]), int(g[1]), int(g[2])
            elif kind == "ym":
                y, mo, d = int(g[0]), int(g[1]), None
            elif kind == "mdy":
                y, mo, d = int(g[2]), MONTHS[g[0].lower()], int(g[1])
            elif kind == "dmy":
                y, mo, d = int(g[2]), MONTHS[g[1].lower()], int(g[0])
            else:
                y, mo, d = int(g[1]), MONTHS[g[0].lower()], None
            try:
                date(y, mo, d or 1)
            except ValueError:
                continue
            taken.append((m.start(), m.end()))
            out.append((y, mo, d))
    return out


def _same_period(a: tuple[int, int, int | None], b: tuple[int, int, int | None], grain: str | None) -> bool:
    """Equal at the requested granularity. A month written without a day ("2025-10", "October 2025")
    only identifies a month, so it can never satisfy a daily request."""
    (ya, ma, da), (yb, mb, db) = a, b
    if grain == "day":
        return da is not None and db is not None and (ya, ma, da) == (yb, mb, db)
    if grain == "week":
        if da is None or db is None:
            return False
        return date(ya, ma, da).isocalendar()[:2] == date(yb, mb, db).isocalendar()[:2]
    if grain == "quarter":
        return (ya, (ma - 1) // 3) == (yb, (mb - 1) // 3)
    if grain == "year":
        return ya == yb
    return (ya, ma) == (yb, mb)  # month, or unspecified: month resolution (as before)


def _entity_match(a: Any, b: Any, grain: str | None = None) -> bool:
    """Do two entities name the same thing? Dates are compared at ``grain`` (month when not given)."""
    if a is None or b is None:
        return False
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return True
    da, db = date_refs(a), date_refs(b)
    if da and db:
        return _same_period(da[0], db[0], grain)
    return False


def entity_stated(entity: Any, text: Any, grain: str | None = None) -> bool:
    """Is ``entity`` stated in ``text``: literally, or, for a date, as any equivalent date there."""
    if entity in (None, "") or not text:
        return False
    if _norm(entity) in _norm(text):
        return True
    want = date_refs(entity)
    return bool(want) and any(_same_period(want[0], d, grain) for d in date_refs(text))


def _refs(e: dict[str, Any]) -> str:
    return json.dumps({"args": e.get("args"), "sql": e.get("sql"),
                       "dims": (e.get("data") or {}).get("dimensions") if isinstance(e.get("data"), dict) else None},
                      default=str).lower()


def _expected_entity(e: dict[str, Any], dimension: str, direction: str, metric: str | None) -> tuple[Any, str] | None:
    """Recompute the primary entity from one piece of evidence, if its shape allows it."""
    data = e.get("data")
    if not isinstance(data, dict):
        return None
    if e.get("tool") == "period_comparison" and data.get("dimensions") == [dimension]:
        rows = data.get("segments") or []
        if rows:
            pick = (min if direction in LOW else max)(rows, key=lambda r: r.get("delta") or 0)
            return pick.get(dimension), f"{e['id']} ({'largest decline' if direction in LOW else 'largest increase'})"
    if e.get("tool") == "compare_groups" and data.get("group_column") == dimension and data.get("groups"):
        pick = (min if direction in LOW else max)(data["groups"], key=lambda g: g.get("mean") or 0)
        return pick.get("group"), f"{e['id']} ({'lowest' if direction in LOW else 'highest'} mean)"
    cols, rows = data.get("columns"), data.get("rows")
    if isinstance(cols, list) and rows and dimension in cols and not isinstance(cols[0], dict):
        di = cols.index(dimension)
        numeric = [i for i, c in enumerate(cols) if i != di and all(
            isinstance(r[i], (int, float)) and not isinstance(r[i], bool) for r in rows if r[i] is not None)]
        if not numeric or len({r[di] for r in rows}) != len(rows):
            return None  # one row per entity is required to rank unambiguously
        if direction in CHANGE_DIRECTIONS:
            pref = [i for i in numeric if re.search(r"delta|change|diff|growth|pct", str(cols[i]), re.I)]
        else:
            pref = [i for i in numeric if metric and metric.lower() in str(cols[i]).lower()]
        if not pref:
            if len(numeric) != 1:
                return None
            pref = numeric
        vi = pref[0]
        valid = [r for r in rows if r[vi] is not None]
        if not valid:
            return None
        pick = (min if direction in LOW else max)(valid, key=lambda r: r[vi])
        return pick[di], f"{e['id']} ({cols[vi]})"
    return None


# --------------------------------------------------------------------------- the check
def check_alignment(spec: TaskSpec, synthesis: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    answer = synthesis.get("answer") or {}
    by_id = {e["id"]: e for e in evidence if e.get("ok")}
    cited_ids = list(dict.fromkeys((answer.get("evidence_ids") or []) +
                                   [i for f in synthesis.get("findings", []) for i in (f.get("evidence_ids") or [])]))
    cited = [by_id[i] for i in cited_ids if i in by_id and by_id[i]["tool"] not in ("profile_dataset", "create_chart")]
    checks: dict[str, str] = {}
    issues: list[str] = []
    text = " ".join([synthesis.get("summary", "")] + [f.get("statement", "") for f in synthesis.get("findings", [])])

    # ---- period
    p_issues: list[str] = []
    if spec.current:
        cur_s, cur_e = date.fromisoformat(spec.current["start"]), date.fromisoformat(spec.current["end"])
        want = [spec.current["start"], spec.current["end"]]
        got = answer.get("current_period")
        ok = bool(got) and list(got)[:2] == want
        if spec.previous:
            ok = ok and list(answer.get("previous_period") or [])[:2] == [spec.previous["start"], spec.previous["end"]]
        if not ok:
            p_issues.append(f"answer periods {got}/{answer.get('previous_period')} differ from the requested "
                          f"{spec.current['label']} {want}" + (f" vs {spec.previous['label']}" if spec.previous else ""))
        win_s, win_e = spec.window()
        covering = []
        for e in cited:
            ds = _dates_in({"a": e.get("args"), "s": e.get("sql")}) + _dates_in(
                (e.get("preview") or {}).get("rows") or [])
            if not ds:
                continue
            outside = [d for d in ds if not (win_s - timedelta(days=1) <= d <= win_e)]
            if outside and not any(cur_s <= d < cur_e for d in ds):
                p_issues.append(f"{e['id']} analyses {min(ds)}..{max(ds)}, outside the requested window "
                              f"[{win_s}, {win_e})")
            if any(cur_s <= d < cur_e for d in ds) or (e["tool"] == "period_comparison" and
                                                       (e.get("args") or {}).get("current_start") == spec.current["start"]):
                covering.append(e["id"])
        if not covering:
            p_issues.append(f"no cited evidence covers the requested period {spec.current['label']}")
        stray = [lbl for lbl, s, e in _mentioned_periods(text) if not (s >= win_s and e <= win_e)]
        if stray:
            p_issues.append(f"answer text discusses periods outside the request: {', '.join(dict.fromkeys(stray))}")
        checks["period"] = "fail" if p_issues else "pass"
        issues += p_issues
    else:
        checks["period"] = "n/a"

    # ---- metric
    if spec.metric_column:
        m = spec.metric_column.lower()
        bad = []
        if answer.get("metric_column") and _norm(answer["metric_column"]) != m:
            bad.append(f"answer uses metric '{answer['metric_column']}' instead of '{spec.metric_column}'")
        if cited and not any(m in _refs(e) for e in cited):
            bad.append(f"no cited evidence uses the metric '{spec.metric_column}'")
        issues += bad
        checks["metric"] = "fail" if bad else "pass"
    else:
        checks["metric"] = "n/a"

    # ---- grouping
    grain = spec.grain()
    if spec.group_by:
        bad = []
        dim = answer.get("dimension")
        wanted = {g.lower() for g in spec.group_by}
        derived = derived_time_groupings(cited)
        if dim and dim not in spec.group_by:
            d = derived.get(str(dim).lower())
            if d is None:
                bad.append(f"answer is grouped by '{dim}' but the question asks for {', '.join(spec.group_by)}")
            elif d[1] not in wanted:
                bad.append(f"answer is grouped by '{dim}' ({d[0]} of {d[1]}) but the question asks for "
                           f"{', '.join(spec.group_by)}")
            elif grain and d[0] != grain:
                bad.append(f"answer is grouped by {d[0]} of {d[1]} but the question asks for {_ADJ[grain]} analysis")
        # a requested granularity must be the one the cited evidence aggregates the date column to
        if grain and not bad:
            buckets = {g for g, col in derived.values() if col in wanted}
            if buckets and grain not in buckets:
                bad.append(f"cited evidence aggregates {', '.join(sorted(wanted))} by {', '.join(sorted(buckets))} "
                           f"but the question asks for {_ADJ[grain]} analysis")
        if cited and not any(all(g.lower() in _refs(e) for g in spec.group_by) for e in cited):
            bad.append(f"no cited evidence is grouped by {', '.join(spec.group_by)}")
        issues += bad
        checks["grouping"] = "fail" if bad else "pass"
    else:
        checks["grouping"] = "n/a"

    # ---- primary conclusion
    entity, dim, direction = answer.get("primary_entity"), answer.get("dimension"), (answer.get("direction") or "")
    if entity in (None, ""):
        if spec.answer_target:
            issues.append("the answer states no primary conclusion (answer.primary_entity is empty)")
            checks["primary_conclusion"] = "fail"
        else:
            checks["primary_conclusion"] = "n/a"
    else:
        recomputed = None
        if dim and direction:
            for e in cited:
                r = _expected_entity(e, dim, direction, spec.metric_column)
                if r is not None:
                    recomputed = r
                    break
        if recomputed is not None and not _entity_match(recomputed[0], entity, grain):
            issues.append(f"primary conclusion '{entity}' contradicts {recomputed[1]}, which points to "
                          f"'{recomputed[0]}'")
            checks["primary_conclusion"] = "fail"
        elif not entity_stated(entity, synthesis.get("summary", ""), grain):
            issues.append(f"the summary does not state the primary conclusion '{entity}'")
            checks["primary_conclusion"] = "fail"
        else:
            checks["primary_conclusion"] = "pass" if recomputed is not None else "unverified"
    status = "misaligned" if issues else "aligned"
    return {"status": status, "checks": checks, "issues": issues, "cited_evidence": cited_ids}
