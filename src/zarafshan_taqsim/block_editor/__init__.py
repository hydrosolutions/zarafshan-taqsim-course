"""A no-code block editor for TaqSim: draw the network, set the numbers, read the result.

The editor is one widget (`BlockEditor`) that runs in Jupyter, Colab and marimo. The canvas lives in
`editor.js`; this package turns the drawing into a TaqSim `WaterSystem`, runs it and sends figures back.
"""

from zarafshan_taqsim.block_editor.compile import build, check, to_python
from zarafshan_taqsim.block_editor.widget import BlockEditor

__all__ = ["BlockEditor", "build", "check", "to_python"]
