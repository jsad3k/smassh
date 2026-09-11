from datetime import date, datetime, timedelta
from typing import Any, ClassVar, Dict, List, Literal, Optional, Set, Tuple
from rich.text import Text
from textual import on
from textual.app import ComposeResult, events
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Digits, Label, ListItem, ListView, Static
from smassh.src.parser import data_parser, TestRecord
from smassh.ui.widgets import BaseWindow, Carousel, CarouselPane

MODE_ICON = {"words": "󰯬", "time": "󰥔"}
_MODIFIER_ICON = {"numbers": "󰲰", "punctuation": "󰸥"}
_CROWN_ICON = ""  # nf-fa-crown


def is_today(day: date) -> bool:
    return day == datetime.now().date()


def _day_label(day: date) -> str:
    if is_today(day):
        return "Today"
    if day == datetime.now().date() - timedelta(days=1):
        return "Yesterday"
    return day.strftime("%Y-%m-%d")


def _format_duration(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


_MODES = ["words", "time"]
_COUNTS = [15, 30, 60, 120]


class BestCard(Widget):
    """
    Card for one (mode, count) combination; uses border_title for the header.
    """

    DEFAULT_CSS = """
    BestCard {
        width: 1fr;
        height: 7;
        margin: 0 1;
        padding: 0 0;
        layout: vertical;
    }

    BestCard .card-values {
        layout: horizontal;
        height: 4;
        width: 1fr;
        align: center middle;
    }

    BestCard .card-stat {
        width: 1fr;
        height: 4;
        layout: vertical;
        align: center middle;
    }

    BestCard .stat-label {
        width: 1fr;
        height: 1;
        content-align: center middle;
    }

    BestCard Digits {
        width: 1fr;
        height: 3;
        text-align: center;
    }

    BestCard .date-label {
        width: 1fr;
        height: 1;
        content-align: center middle;
    }
    """

    def __init__(
        self,
        mode: str,
        count: int,
        wpm: Optional[int],
        accuracy: Optional[int],
        start_time: Optional[float] = None,
    ) -> None:
        super().__init__()
        unit = "s" if mode == "time" else ""
        self.border_title = f" {MODE_ICON[mode]} {mode} · {count}{unit} "
        self._wpm = str(wpm) if wpm is not None else "--"
        self._accuracy = str(accuracy) if accuracy is not None else "--"
        if start_time is not None:
            day = datetime.fromtimestamp(start_time).date()
            self._date = day.strftime("%Y-%m-%d")
            self._is_today = is_today(day)
        else:
            self._date = ""
            self._is_today = False
        if wpm is None:
            self.add_class("empty")

    def on_mount(self) -> None:
        if self._is_today:
            self.add_class("today")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="card-values"):
            with Vertical(classes="card-stat"):
                yield Label("wpm", classes="stat-label")
                yield Digits(self._wpm)
            with Vertical(classes="card-stat"):
                yield Label("acc%", classes="stat-label")
                yield Digits(self._accuracy)
        yield Label(self._date, classes="date-label")


class BestRow(Horizontal):
    """
    One centered row of 4 BestCards for a single mode.
    """

    DEFAULT_CSS = """
    BestRow {
        height: 7;
        width: 1fr;
        align: center middle;
    }
    """


class BestScores(Widget):
    """
    Two rows of best-score cards: words (top) and time (bottom).
    """

    DEFAULT_CSS = """
    BestScores {
        layout: vertical;
        height: auto;
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield BestRow(id="words-row")
        yield BestRow(id="time-row")


class SummaryCard(Widget):
    """
    Card for a single aggregate stat (e.g. total tests completed); uses
    border_title for the header.
    """

    DEFAULT_CSS = """
    SummaryCard {
        width: 1fr;
        height: 5;
        margin: 0 1;
        layout: vertical;
        align: center middle;
    }

    SummaryCard Digits {
        width: 1fr;
        height: 3;
        text-align: center;
    }
    """

    def __init__(self, title: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = f" {title} "

    def compose(self) -> ComposeResult:
        yield Digits("--")

    def update_value(self, value: str) -> None:
        self.query_one(Digits).update(value)


class SummaryStats(Horizontal):
    """
    Row of summary cards, shown above the heatmap: total tests completed
    and total time spent typing.
    """

    DEFAULT_CSS = """
    SummaryStats {
        height: 5;
        width: 1fr;
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield SummaryCard("tests completed", id="total-tests-card")
        yield SummaryCard("time typing", id="total-time-card")

    def set_data(self) -> None:
        history = data_parser.history()
        self.query_one("#total-tests-card", SummaryCard).update_value(
            str(history.total_tests())
        )
        self.query_one("#total-time-card", SummaryCard).update_value(
            _format_duration(history.total_time_typing())
        )


class YearHeatmap(Widget):

    COMPONENT_CLASSES: ClassVar[Set[str]] = {
        "year-heatmap--l0",
        "year-heatmap--l1",
        "year-heatmap--l2",
        "year-heatmap--l3",
        "year-heatmap--l4",
        "year-heatmap--l5",
        "year-heatmap--l6",
        "year-heatmap--l7",
        "year-heatmap--l8",
        "year-heatmap--label",
        "year-heatmap--bound",
    }

    DEFAULT_CSS = """
    YearHeatmap { width: 1fr; height: 100%; }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._counts: Dict[date, int] = {}
        self._best_days: set = set()

    def set_data(self) -> None:
        history = data_parser.history()
        self._counts = history.counts_per_day()
        self._best_days = {
            r.day for r in history.bests_by_mode_count().values()
            if r.day is not None
        }
        self.refresh()

    def _level(self, count: int) -> str:
        if count == 0: return "year-heatmap--l0"
        if count == 1: return "year-heatmap--l1"
        if count == 2: return "year-heatmap--l2"
        if count <= 4: return "year-heatmap--l3"
        if count <= 6: return "year-heatmap--l4"
        if count <= 9: return "year-heatmap--l5"
        if count <= 13: return "year-heatmap--l6"
        if count <= 18: return "year-heatmap--l7"
        return "year-heatmap--l8"

    def render(self) -> Text:
        today = datetime.now().date()
        start = today - timedelta(weeks=52)
        start -= timedelta(days=start.weekday())  # align to Monday

        styles = {
            cls: self.get_component_rich_style(cls)
            for cls in self.COMPONENT_CLASSES
        }
        label_s = styles["year-heatmap--label"]

        DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        indent = " " * max(0, (self.size.width - (53 * 2 + 4)) // 2)
        bound_s = styles["year-heatmap--bound"]

        # Pre-compute which week columns are the LAST week of their month
        # (gap goes after the last cell of a month, so no two glyphs are adjacent).
        month_ends: Set[int] = set()
        for week in range(53):
            if (start + timedelta(weeks=week)).month != (start + timedelta(weeks=week + 1)).month:
                month_ends.add(week)

        result = Text()

        # Month label row - stamp 3-char abbreviations into a char buffer so they
        # align exactly with the data column below (position = week * 2).
        char_buf: List[Tuple[str, Any]] = [(" ", None)] * (53 * 2)
        prev_month = -1
        for week in range(53):
            monday = start + timedelta(weeks=week)
            if monday <= today and monday.month != prev_month:
                pos = week * 2
                for i, ch in enumerate(monday.strftime("%b")):
                    if pos + i < len(char_buf):
                        char_buf[pos + i] = (ch, label_s)
                prev_month = monday.month
        result.append(indent)
        result.append("    ")  # y-axis gutter for month label row
        for ch, style in char_buf:
            result.append(ch, style=style)
        result.append("\n")

        # Day-of-week rows (Mon … Sun)
        for dow in range(7):
            result.append(indent)
            result.append(f"{DAY_LABELS[dow]} ", style=label_s)
            for week in range(53):
                day = start + timedelta(weeks=week, days=dow)
                if day > today:
                    result.append("  ")
                else:
                    count = self._counts.get(day, 0)
                    level_s = styles[self._level(count)]
                    glyph = "" if day in self._best_days else ""
                    if week in month_ends:
                        result.append(glyph, style=level_s)
                        result.append(" ", style=bound_s)
                    else:
                        result.append(glyph + " ", style=level_s)
            if dow < 6:
                result.append("\n")

        return result


class HighscorePane(CarouselPane):
    """
    Carousel pane showing the year heatmap and all-time best score cards.
    """

    DEFAULT_CSS = """
    HighscorePane {
        layout: vertical;
        padding: 1 2 0 2;
    }

    HighscorePane VerticalScroll {
        height: 1fr;
    }

    HighscorePane #heatmap_section {
        height: 8;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield SummaryStats()
        with VerticalScroll():
            with Static(id="heatmap_section"):
                yield YearHeatmap(id="year-heatmap")
            yield BestScores()

    async def activate(self) -> None:
        await self._rebuild_best_scores()
        self.query_one(YearHeatmap).set_data()
        self.query_one(SummaryStats).set_data()

    async def handle_key(self, event: events.Key) -> bool:
        scroll = self.query_one(VerticalScroll)
        if event.key == "j":
            event.stop()
            scroll.scroll_down()
            return True
        if event.key == "k":
            event.stop()
            scroll.scroll_up()
            return True
        return False

    async def _rebuild_best_scores(self) -> None:
        bests = data_parser.history().bests_by_mode_count()
        for mode, row_id in [("words", "words-row"), ("time", "time-row")]:
            row = self.query_one(f"#{row_id}", BestRow)
            await row.query(BestCard).remove()
            cards = []
            for count in _COUNTS:
                test = bests.get((mode, count))
                wpm = test.wpm if test else None
                acc = test.accuracy if test else None
                start_time = test.start_time if test else None
                cards.append(BestCard(mode, count, wpm, acc, start_time))
            await row.mount(*cards)


class _NavLeft(Static):
    def on_click(self) -> None:
        self.parent.prev_day()  # type: ignore[union-attr]


class _NavRight(Static):
    def on_click(self) -> None:
        self.parent.next_day()  # type: ignore[union-attr]


class DayNavigator(Widget):
    """
    Shows the currently viewed day with clickable ← / → to change days.
    """

    class DayChanged(Message):
        """Posted when the navigator moves to a different day."""

    DEFAULT_CSS = """
    DayNavigator {
        height: 3;
        width: 1fr;
        layout: horizontal;
        align: center middle;
    }

    DayNavigator .nav-arrow {
        width: 3;
        height: 1;
        content-align: center middle;
    }

    DayNavigator .nav-center {
        width: 1fr;
        height: 1;
        content-align: center middle;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._days: List[date] = []
        self._index: int = 0

    def compose(self) -> ComposeResult:
        yield _NavLeft("←", classes="nav-arrow")
        yield Static("", classes="nav-center", id="nav-label")
        yield _NavRight("→", classes="nav-arrow")

    def on_mount(self) -> None:
        self._refresh_display()

    def load_days(self) -> None:
        today = datetime.now().date()
        days = data_parser.history().days_with_tests()
        if today not in days:
            days = [today] + days
        self._days = days
        try:
            self._index = self._days.index(today)
        except ValueError:
            self._index = 0
        self._refresh_display()

    @property
    def current_day(self) -> date:
        return self._days[self._index] if self._days else datetime.now().date()

    def prev_day(self) -> None:
        if self._days and self._index < len(self._days) - 1:
            self._index += 1
            self._refresh_display()
            self.post_message(self.DayChanged())

    def next_day(self) -> None:
        if self._days and self._index > 0:
            self._index -= 1
            self._refresh_display()
            self.post_message(self.DayChanged())

    def _count_for_day(self, day: date) -> int:
        return data_parser.history().count_for_day(day)

    def _refresh_display(self) -> None:
        day = self.current_day
        count = self._count_for_day(day)
        label = _day_label(day)
        suffix = f"  ·  {count} test{'s' if count != 1 else ''}"
        self.query_one("#nav-label", Static).update(label + suffix)


class TestRecordItem(ListItem):
    """
    Single-line, borderless row for one typing test record.
    """

    COMPONENT_CLASSES: ClassVar[Set[str]] = {
        "test-record-item--time",
        "test-record-item--wpm",
        "test-record-item--dim",
        "test-record-item--pass",
        "test-record-item--fail",
    }

    DEFAULT_CSS = """
    TestRecordItem {
        height: 1;
        width: 1fr;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        test: TestRecord,
        rank: Literal["normal", "best", "highscore"] = "normal",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._test = test
        self._is_best = rank != "normal"

        if rank == "highscore":
            self.add_class("highscore")
        elif rank == "best":
            self.add_class("best")
        if test.failed:
            self.add_class("failed")

    def render(self) -> Text:
        t = self._test
        time_s = self.get_component_rich_style("test-record-item--time")
        wpm_s = self.get_component_rich_style("test-record-item--wpm")
        dim_s = self.get_component_rich_style("test-record-item--dim")
        pass_s = self.get_component_rich_style("test-record-item--pass")
        fail_s = self.get_component_rich_style("test-record-item--fail")

        mode = t.mode
        count = t.count
        unit = "s" if mode == "time" else ""
        lang = t.language

        start = t.start_time
        time_str = datetime.fromtimestamp(start).strftime("%H:%M") if start else "--:--"
        # Reserve the same width whether the crown is shown or not, so the
        # time column lines up across rows.
        marker = f"{_CROWN_ICON}  " if self._is_best else "   "

        result_str = "failed" if t.failed else "passed"
        result_s = fail_s if t.failed else pass_s
        num_s = pass_s if t.numbers else dim_s
        punct_s = pass_s if t.punctuations else dim_s

        sep = "   "
        mode_icon = MODE_ICON.get(mode, "")
        num_icon = _MODIFIER_ICON["numbers"]
        punct_icon = _MODIFIER_ICON["punctuation"]
        # Fixed width so "100%" doesn't push "passed"/"failed" out of line with "9%"/"85%".
        accuracy_str = f"{t.accuracy:>3}%"
        left_str = f"{marker}{time_str}{sep}{t.wpm} wpm{sep}{accuracy_str}{sep}{result_str}"
        right_str = (
            f"{mode_icon} {mode} · {count}{unit}{sep}{lang}"
            f"{sep}{num_icon} numbers{sep}{punct_icon} punctuation"
        )
        gap = max(3, self.content_size.width - len(left_str) - len(right_str))

        return (
            Text(f"{marker}{time_str}{sep}", style=time_s)
            + Text(f"{t.wpm} wpm", style=wpm_s)
            + Text(f"{sep}{accuracy_str}{sep}", style=dim_s)
            + Text(result_str, style=result_s)
            + Text(" " * gap, style=dim_s)
            + Text(f"{mode_icon} {mode} · {count}{unit}{sep}", style=dim_s)
            + Text(lang, style=dim_s)
            + Text(f"{sep}{num_icon} numbers", style=num_s)
            + Text(f"{sep}{punct_icon} punctuation", style=punct_s)
        )


class TestRecordList(ListView, can_focus=False):
    """
    Scrollable list of TestRecordItem rows for a single day. Never focused -
    cursor movement is driven explicitly by TestRecordViewerPane.handle_key.
    """

    DEFAULT_CSS = """
    TestRecordList {
        width: 80%;
        max-width: 120;
        height: auto;
        max-height: 100%;
        scrollbar-size: 0 1;
        scrollbar-gutter: stable;
    }
    """

    async def populate(self, day: date) -> None:
        await self.clear()

        history = data_parser.history()
        day_tests = history.tests_for_day(day)
        best_per_key = history.day_bests(day_tests)
        all_time = history.bests_by_mode_count()

        items: List[ListItem] = []
        for t in day_tests:
            key = (t.mode, t.count)
            is_daily_best = not t.failed and t.wpm == best_per_key.get(key, 0)
            best_record = all_time.get(key)
            is_highscore = (
                best_record is not None
                and not t.failed
                and t.start_time == best_record.start_time
            )
            if is_highscore:
                rank = "highscore"
            elif is_daily_best:
                rank = "best"
            else:
                rank = "normal"
            items.append(TestRecordItem(t, rank))

        if items:
            await self.extend(items)
            self.index = 0
        else:
            await self.extend([ListItem(Label("no tests for this day", classes="no-data"))])


class TestRecordViewerPane(CarouselPane):
    """
    Daily test record browser; lives beside HighscorePane inside a Carousel.
    """

    DEFAULT_CSS = """
    TestRecordViewerPane {
        layout: vertical;
        padding: 0 2;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }

    TestRecordViewerPane DayNavigator {
        margin-bottom: 1;
    }

    TestRecordViewerPane #record-list-area {
        height: 1fr;
        align: center top;
    }
    """

    def compose(self) -> ComposeResult:
        yield DayNavigator(id="day-navigator")
        with Vertical(id="record-list-area"):
            yield TestRecordList(id="test-record-list")

    async def activate(self) -> None:
        self.query_one(DayNavigator).load_days()
        await self.refresh_records()

    async def refresh_records(self) -> None:
        day = self.query_one(DayNavigator).current_day
        await self.query_one(TestRecordList).populate(day)

    @on(DayNavigator.DayChanged)
    async def _on_day_changed(self) -> None:
        await self.refresh_records()

    async def handle_key(self, event: events.Key) -> bool:
        if event.key == "h":
            event.stop()
            self.query_one(DayNavigator).prev_day()
        elif event.key == "l":
            event.stop()
            self.query_one(DayNavigator).next_day()
        elif event.key == "j":
            event.stop()
            self.query_one(TestRecordList).action_cursor_down()
        elif event.key == "k":
            event.stop()
            self.query_one(TestRecordList).action_cursor_up()
        else:
            return False
        return True


class HighscoreScreen(BaseWindow):
    """
    Screen hosting a Carousel that slides between the highscore overview
    and the daily test-record browser.
    """

    def compose(self) -> ComposeResult:
        yield Carousel([HighscorePane(), TestRecordViewerPane()])

    async def handle_key(self, event: events.Key) -> bool:
        if await super().handle_key(event):
            return True
        return await self.query_one(Carousel).handle_key(event)
