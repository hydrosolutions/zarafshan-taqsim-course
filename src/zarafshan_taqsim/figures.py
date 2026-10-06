"""Notebook figure and table captions with stable anchors.

This module is intentionally small and notebook-oriented. It mirrors the
caption workflow used in the groundwater/surface-water notebooks: display a
figure or table, then show a numbered HTML caption with an optional anchor.
Matplotlib figures are closed after display to avoid duplicate inline rendering.
"""

from __future__ import annotations

from html import escape
from re import sub
from typing import Any


class FigureRegistry:
    """Auto-numbered figure captions for Jupyter notebooks."""

    def __init__(self) -> None:
        self._count = 0
        self._labels: dict[str, int] = {}

    def caption(self, fig: Any, text: str, *, label: str | None = None) -> None:
        """Display a figure followed by a numbered caption.

        Parameters
        ----------
        fig
            Matplotlib or Plotly figure-like object.
        text
            Caption text. It is HTML-escaped before display.
        label
            Optional anchor label. A label of ``"network"`` creates
            ``#fig-network`` for notebook links.
        """
        self._count += 1
        number = self._count
        if label:
            self._labels[label] = number

        try:
            from IPython.display import HTML, display
        except ImportError:
            self._fallback_display(fig)
            print(f"Figure {number}: {self._plain_text(text)}")
            return

        display(fig)
        if hasattr(fig, "savefig"):
            self._close_matplotlib_figure(fig)

        anchor = f' id="fig-{escape(label, quote=True)}"' if label else ""
        display(
            HTML(
                f'<p{anchor} style="text-align:center; font-style:italic; '
                f'color:#555; margin-top:4px;">'
                f"<b>Figure {number}</b>: {escape(text)}</p>"
            )
        )

    def ref(self, label: str) -> str:
        """Return a Markdown reference to a labelled notebook figure."""
        number = self._labels.get(label)
        if number is None:
            return f"Figure ?? ({label})"
        return f"[Figure {number}](#fig-{label})"

    def references(self) -> None:
        """Print all known labels and figure numbers."""
        if not self._labels:
            print("No labelled figures registered yet.")
            return
        for label, number in self._labels.items():
            print(f"Figure {number}: #{label}")

    def reset(self, *, start: int = 0) -> None:
        """Reset numbering for a fresh notebook run."""
        self._count = start
        self._labels.clear()

    @staticmethod
    def _close_matplotlib_figure(fig: Any) -> None:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            return
        plt.close(fig)

    @staticmethod
    def _fallback_display(fig: Any) -> None:
        show = getattr(fig, "show", None)
        if callable(show):
            show()

    @staticmethod
    def _plain_text(text: str) -> str:
        return sub(r"<[^>]+>", "", text)


figures = FigureRegistry()


class TableRegistry:
    """Auto-numbered table captions for Jupyter notebooks."""

    def __init__(self) -> None:
        self._count = 0
        self._labels: dict[str, int] = {}

    def caption(self, table: Any, text: str, *, label: str | None = None) -> None:
        """Display a table with a numbered caption above it.

        Parameters
        ----------
        table
            Pandas DataFrame, Styler, or another Jupyter-displayable table-like
            object.
        text
            Caption text. It is HTML-escaped before display.
        label
            Optional anchor label. A label of ``"summary"`` creates
            ``#tbl-summary`` for notebook links.
        """
        self._count += 1
        number = self._count
        if label:
            self._labels[label] = number

        try:
            from IPython.display import HTML, display
        except ImportError:
            print(f"Table {number}: {self._plain_text(text)}")
            print(table)
            return

        anchor = f' id="tbl-{escape(label, quote=True)}"' if label else ""
        display(
            HTML(
                f'<p{anchor} style="font-style:italic; color:#555; '
                f'margin-bottom:6px;">'
                f"<b>Table {number}</b>: {escape(text)}</p>"
            )
        )
        display(table)

    def ref(self, label: str) -> str:
        """Return a Markdown reference to a labelled notebook table."""
        number = self._labels.get(label)
        if number is None:
            return f"Table ?? ({label})"
        return f"[Table {number}](#tbl-{label})"

    def references(self) -> None:
        """Print all known labels and table numbers."""
        if not self._labels:
            print("No labelled tables registered yet.")
            return
        for label, number in self._labels.items():
            print(f"Table {number}: #{label}")

    def reset(self, *, start: int = 0) -> None:
        """Reset numbering for a fresh notebook run."""
        self._count = start
        self._labels.clear()

    @staticmethod
    def _plain_text(text: str) -> str:
        return sub(r"<[^>]+>", "", text)


tables = TableRegistry()
