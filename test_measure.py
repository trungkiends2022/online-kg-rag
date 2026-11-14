import subprocess
import re

# Let's write a TikZ standalone that prints the coordinates of nodes to the log or aux
tex = r"""\documentclass{standalone}
\usepackage{tikz}
\usetikzlibrary{calc,positioning}
\begin{document}
\input{diagnostic-l2-diagram}
\end{document}
"""
