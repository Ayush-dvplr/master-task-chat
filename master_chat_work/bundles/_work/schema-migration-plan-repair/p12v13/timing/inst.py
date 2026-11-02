"""Copy tests/test_output.py with an atexit line printing the child budget left and the wall time."""
import sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
text += '\n\nimport atexit as _ax, time as _tm\n_T0 = _tm.monotonic()\n_ax.register(lambda: print("BUDGET_LEFT", round(_CHILD_SECONDS["left"], 2), "WALL", round(_tm.monotonic() - _T0, 1), flush=True))\n'
dst.write_text(text, encoding="utf-8")
