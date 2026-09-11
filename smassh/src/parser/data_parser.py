from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional
from .parser import Parser
from smassh.src.stats_tracker import StatsTracker
from smassh.src.parser.config_parser import config_parser
import platformdirs


@dataclass
class TestRecord:
    mode: str
    count: int
    start_time: Optional[float]
    elapsed_time: float
    wpm: int
    raw_wpm: int
    accuracy: int
    numbers: bool
    punctuations: bool
    language: str
    failed: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "TestRecord":
        return cls(
            mode=d.get("mode", "words"),
            count=d.get("count", 30),
            start_time=d.get("start_time"),
            elapsed_time=d.get("elapsed_time", 0.0),
            wpm=d.get("wpm", 0),
            raw_wpm=d.get("raw_wpm", 0),
            accuracy=d.get("accuracy", 0),
            numbers=bool(d.get("numbers", False)),
            punctuations=bool(d.get("punctuations", False)),
            language=d.get("language", "english"),
            failed=bool(d.get("failed", False)),
        )

    @property
    def day(self) -> Optional[date]:
        if not self.start_time:
            return None
        return datetime.fromtimestamp(self.start_time).date()


class DataParser(Parser):
    """
    Inherited from `Parser` class to manage user data
    """

    config_path = Path(platformdirs.user_data_dir("smassh"))
    lang_path = config_path / "languages"
    DEFAULT_CONFIG = dict(data=[])

    def __init__(self) -> None:
        super().__init__()
        self._history_cache: Optional["TestRecords"] = None

        english_path = self.lang_path / "english.json"

        if not self.lang_path.is_dir():
            self.lang_path.mkdir(parents=True, exist_ok=True)

        if not english_path.exists():
            from smassh.src.plugins.add_language import AddLanguage

            AddLanguage(silent=True).add("english")

    def tests(self) -> List[TestRecord]:
        return [TestRecord.from_dict(d) for d in self.get("data") or []]

    def generate_report(self, stats: StatsTracker) -> TestRecord:
        mode = config_parser.get("mode")
        count = config_parser.get(f"{mode}_count")
        start = stats.start_time or 0
        end = stats.end_time or 0

        return TestRecord(
            mode=mode,
            count=count,
            start_time=stats.start_time,
            elapsed_time=end - start,
            wpm=stats.wpm,
            raw_wpm=stats.raw_wpm,
            accuracy=stats.accuracy,
            numbers=bool(config_parser.get("numbers")),
            punctuations=bool(config_parser.get("punctuations")),
            language=config_parser.get("language"),
        )

    def add_stats(self, stats: StatsTracker, failed: bool) -> None:
        record = self.generate_report(stats)
        record.failed = failed
        self.get("data").append(asdict(record))
        self.save()
        self._history_cache = None

    def history(self) -> "TestRecords":
        from smassh.src.parser.test_records import TestRecords
        if self._history_cache is None:
            self._history_cache = TestRecords(self.tests())
        return self._history_cache


data_parser = DataParser()
