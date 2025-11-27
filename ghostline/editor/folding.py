"""Simple folding manager for CodeEditor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6.QtGui import QTextBlock
from PySide6.QtWidgets import QPlainTextEdit


@dataclass
class FoldingRegion:
    start: int
    end: int
    collapsed: bool = False


class FoldingManager:
    """Creates naive folding regions based on bracket pairs."""

    def __init__(self, editor: QPlainTextEdit) -> None:
        self.editor = editor
        self.regions: List[FoldingRegion] = []
        self.editor.textChanged.connect(self.recompute)
        self.recompute()

    def recompute(self) -> None:
        text = self.editor.toPlainText()
        stack: list[int] = []
        regions: List[FoldingRegion] = []
        for idx, char in enumerate(text):
            if char == "{":
                block = self.editor.document().findBlock(idx)
                stack.append(block.blockNumber())
            elif char == "}" and stack:
                start_line = stack.pop()
                end_block = self.editor.document().findBlock(idx)
                if end_block.blockNumber() > start_line:
                    regions.append(FoldingRegion(start_line, end_block.blockNumber()))
        self.regions = regions

    def toggle_at_line(self, line: int) -> None:
        for region in self.regions:
            if region.start == line:
                region.collapsed = not region.collapsed
                self._apply_region(region)
                break

    def _apply_region(self, region: FoldingRegion) -> None:
        block: QTextBlock = self.editor.document().findBlockByNumber(region.start + 1)
        while block.isValid() and block.blockNumber() <= region.end:
            block.setVisible(not region.collapsed)
            block = block.next()
        self.editor.viewport().update()
