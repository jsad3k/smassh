from typing import Any, List
from textual.app import ComposeResult, events
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static


class CarouselPane(Widget):
    """
    Base class for widgets used as Carousel panes. `activate`/`handle_key`
    default to no-ops; override either as needed.
    """

    async def activate(self) -> None:
        """Called by the owning Carousel when this pane becomes active."""

    async def handle_key(self, event: events.Key) -> bool:
        """Called by the owning Carousel for keys it doesn't itself handle.

        Returns True if the key was handled.
        """
        return False


class CarouselPager(Static):
    """
    Dot pager + keybind hint docked at the bottom of a Carousel, showing
    which pane (of how many) is currently in view.
    """

    DEFAULT_CSS = """
    CarouselPager {
        dock: bottom;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    """

    def __init__(self, pane_count: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pane_count = pane_count

    def set_pane(self, index: int) -> None:
        dots = " ".join("●" if i == index else "○" for i in range(self._pane_count))
        hints = []
        if index > 0:
            hints.append("← shift+h")
        if index < self._pane_count - 1:
            hints.append("shift+l →")
        self.update("   ".join([dots, *hints]))

    def on_mount(self) -> None:
        self.set_pane(0)


class Carousel(Horizontal):
    """
    Generic sliding viewport showing one of several panes at a time, with a
    dot pager docked at the bottom. shift+L/H slide between adjacent panes.
    """

    DEFAULT_CSS = """
    Carousel {
        width: 1fr;
        height: 1fr;
        overflow-x: hidden;
        overflow-y: hidden;
    }

    Carousel > .carousel-pane {
        width: 100%;
        height: 100%;
        min-width: 100%;
    }
    """

    def __init__(self, panes: List[CarouselPane], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._panes = panes
        self._current_pane = 0

    @property
    def current_pane(self) -> int:
        """Index of the currently active pane."""
        return self._current_pane

    def compose(self) -> ComposeResult:
        for pane in self._panes:
            pane.add_class("carousel-pane")
            yield pane
        yield CarouselPager(len(self._panes))

    async def on_show(self) -> None:
        # Re-activate whichever pane was last shown (0 on first show) instead
        # of always snapping back to pane 0, so re-entering the Carousel
        # (e.g. leaving and reopening the screen) preserves pane position.
        await self.show_pane(self._current_pane, animate=False)

    async def show_pane(self, index: int, animate: bool = True) -> None:
        if not 0 <= index < len(self._panes):
            return
        self._current_pane = index
        self.scroll_to(
            x=self.size.width * index,
            animate=animate,
            duration=0.28,
            easing="out_cubic",
            force=True,
        )
        self.query_one(CarouselPager).set_pane(index)
        await self._panes[index].activate()

    async def handle_key(self, event: events.Key) -> bool:
        if event.key == "L" and self._current_pane < len(self._panes) - 1:
            event.stop()
            await self.show_pane(self._current_pane + 1)
            return True
        if event.key == "H" and self._current_pane > 0:
            event.stop()
            await self.show_pane(self._current_pane - 1)
            return True
        return await self._panes[self._current_pane].handle_key(event)
