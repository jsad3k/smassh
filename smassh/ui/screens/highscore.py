from datetime import date, datetime, timedelta
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple
from rich.text import Text
from textual.app import ComposeResult, events
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Digits, Label, Static
from smassh.src.parser import data_parser
from smassh.ui.widgets import BaseWindow, Carousel, CarouselPane

MODE_ICON = {"words": "󰯬", "time": "󰥔"}


def is_today(day: date) -> bool:
    return day == datetime.now().date()


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


class HighscoreScreen(BaseWindow):
    """
    Screen hosting a Carousel showing the highscore overview.
    """

    def compose(self) -> ComposeResult:
        yield Carousel([HighscorePane()])

    async def handle_key(self, event: events.Key) -> bool:
        if await super().handle_key(event):
            return True
        return await self.query_one(Carousel).handle_key(event)
