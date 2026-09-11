from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple
from .data_parser import TestRecord


class TestRecords:
    """
    Snapshot analytics over a list of TestRecord objects.

    The snapshot is immutable for its lifetime (DataParser hands out a fresh
    instance whenever the underlying data changes), so derived views below
    are computed once and cached rather than re-scanned on every call.
    """

    def __init__(self, tests: List[TestRecord]) -> None:
        self._tests = tests
        self._bests_by_mode_count: Optional[Dict[Tuple[str, int], TestRecord]] = None
        self._tests_by_day: Optional[Dict[date, List[TestRecord]]] = None

    @staticmethod
    def _best_by_mode_count(tests: Iterable[TestRecord]) -> Dict[Tuple[str, int], TestRecord]:
        """Best non-failed TestRecord per (mode, count) within the given tests."""
        bests: Dict[Tuple[str, int], TestRecord] = {}
        for t in tests:
            if t.failed:
                continue
            key = (t.mode, t.count)
            if key not in bests or t.wpm > bests[key].wpm:
                bests[key] = t
        return bests

    def bests_by_mode_count(self) -> Dict[Tuple[str, int], TestRecord]:
        """All-time best non-failed attempt per (mode, count)."""
        if self._bests_by_mode_count is None:
            self._bests_by_mode_count = self._best_by_mode_count(self._tests)
        return self._bests_by_mode_count

    def _by_day(self) -> Dict[date, List[TestRecord]]:
        """Tests grouped by calendar day, computed once per snapshot."""
        if self._tests_by_day is None:
            by_day: Dict[date, List[TestRecord]] = {}
            for t in self._tests:
                if t.day is not None:
                    by_day.setdefault(t.day, []).append(t)
            self._tests_by_day = by_day
        return self._tests_by_day

    def tests_for_day(self, day: date) -> List[TestRecord]:
        """Tests on a given day, sorted newest-first."""
        return sorted(
            self._by_day().get(day, []),
            key=lambda t: (t.start_time or 0),
            reverse=True,
        )

    def day_bests(self, tests: Iterable[TestRecord]) -> Dict[Tuple[str, int], int]:
        """Best WPM per (mode, count) for non-failed tests among the given tests."""
        return {key: record.wpm for key, record in self._best_by_mode_count(tests).items()}

    def counts_per_day(self) -> Dict[date, int]:
        """Number of attempts per calendar day."""
        return {day: len(tests) for day, tests in self._by_day().items()}

    def total_tests(self) -> int:
        """Total number of completed (non-failed) tests."""
        return sum(1 for t in self._tests if not t.failed)

    def total_time_typing(self) -> float:
        """Total elapsed time spent typing across all attempts, in seconds."""
        return sum(t.elapsed_time for t in self._tests)

    def days_with_tests(self) -> List[date]:
        """Unique days (newest-first) that have at least one test."""
        return sorted(self._by_day(), reverse=True)

    def count_for_day(self, day: date) -> int:
        """Number of tests on a given day."""
        return len(self._by_day().get(day, []))

    def filter_by(self, mode: str, count: int) -> List[TestRecord]:
        """Non-failed tests matching mode and count."""
        return [t for t in self._tests if t.mode == mode and t.count == count and not t.failed]

    def best_wpm(self, mode: str, count: int) -> int:
        tests = self.filter_by(mode, count)
        if not tests:
            return 0
        return max(tests, key=lambda x: x.wpm).wpm

    def best_accuracy(self, mode: str, count: int) -> int:
        tests = self.filter_by(mode, count)
        if not tests:
            return 0
        return max(tests, key=lambda x: x.accuracy).accuracy

    def is_personal_best_wpm(self, wpm: int, mode: str, count: int) -> bool:
        return wpm > self.best_wpm(mode, count)

    def is_personal_best_accuracy(self, accuracy: int, mode: str, count: int) -> bool:
        return accuracy > self.best_accuracy(mode, count)
