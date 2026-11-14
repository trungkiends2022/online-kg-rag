import subprocess

latex_content = r"""\documentclass[tikz,border=2mm]{standalone}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,positioning,shapes.geometric,fit,backgrounds,calc}
\usepackage{lmodern}

\begin{document}
\begin{tikzpicture}[
  >=Latex,
  font=\sffamily\scriptsize,
  % Column Panels
  tier_col/.style={draw=#1!70!black, fill=#1!2!white, rounded corners=6pt, line width=0.7pt},
  col_header/.style={fill=#1!14, draw=#1!70!black, line width=0.5pt, rounded corners=3pt, font=\bfseries\scriptsize, text=#1!95!black, inner sep=2.5pt, align=center},
  % Algorithmic Blocks
  alg_io/.style={draw=#1!75!black, fill=white, rounded corners=3.5pt, line width=0.55pt, inner sep=3pt, align=left},
  alg_proc/.style={draw=#1!80!black, fill=#1!7, rounded corners=3.5pt, line width=0.6pt, inner sep=3pt, align=left},
  alg_decision/.style={diamond, aspect=2.1, draw=#1!85!black, fill=#1!12, line width=0.6pt, inner sep=1.5pt, font=\fontsize{4.8pt}{5.6pt}\selectfont\bfseries, text=#1!95!black, align=center},
  alg_exit/.style={draw=green!70!black, fill=green!12, rounded corners=3pt, line width=0.65pt, inner sep=2.5pt, align=center, font=\bfseries\scriptsize, text=green!90!black},
  % Arrows
  flow/.style={->, line width=0.95pt, draw=gray!70!black},
  flow_blue/.style={->, line width=0.95pt, draw=blue!75!black},
  flow_teal/.style={->, line width=0.95pt, draw=teal!80!black},
  flow_orange/.style={->, line width=1.05pt, draw=orange!85!black},
  flow_green/.style={->, line width=1.1pt, draw=green!65!black},
  handoff_wire/.style={->, line width=1.1pt, draw=orange!90!black}
]

% ==========================================================
% ICON MACROS
% ==========================================================

% Brain Icon: #1 = position, #2 = scale, #3 = color
\def\drawbrain#1#2#3{
  \begin{scope}[shift={(#1)}, scale=#2]
    % Left hemisphere
    \draw[fill=#3!20, draw=#3!85!black, line width=0.65pt]
      (0, 0.72) 
      .. controls (-0.35, 0.82) and (-0.72, 0.62) .. (-0.72, 0.28)
      .. controls (-0.92, 0.12) and (-0.92, -0.22) .. (-0.68, -0.34)
      .. controls (-0.76, -0.58) and (-0.52, -0.78) .. (-0.28, -0.68)
      .. controls (-0.18, -0.82) and (-0.05, -0.68) .. (0, -0.58)
      -- cycle;
    % Right hemisphere
    \draw[fill=#3!20, draw=#3!85!black, line width=0.65pt]
      (0, 0.72) 
      .. controls (0.35, 0.82) and (0.72, 0.62) .. (0.72, 0.28)
      .. controls (0.92, 0.12) and (0.92, -0.22) .. (0.68, -0.34)
      .. controls (0.76, -0.58) and (0.52, -0.78) .. (0.28, -0.68)
      .. controls (0.18, -0.82) and (0.05, -0.68) .. (0, -0.58)
      -- cycle;
    % Midline
    \draw[#3!85!black, line width=0.65pt] (0, 0.70) -- (0, -0.56);
    % Neural nodes & synapses (Left)
    \fill[#3!85!black] (-0.32, 0.36) circle (1.0pt);
    \fill[#3!85!black] (-0.50, 0.02) circle (1.0pt);
    \fill[#3!85!black] (-0.22, -0.12) circle (1.0pt);
    \fill[#3!85!black] (-0.38, -0.42) circle (1.0pt);
    \draw[#3!65!black, line width=0.35pt] (-0.32, 0.36) -- (-0.50, 0.02) -- (-0.22, -0.12) -- (-0.38, -0.42);
    % Neural nodes & synapses (Right)
    \fill[#3!85!black] (0.32, 0.36) circle (1.0pt);
    \fill[#3!85!black] (0.50, 0.02) circle (1.0pt);
    \fill[#3!85!black] (0.22, -0.12) circle (1.0pt);
    \fill[#3!85!black] (0.38, -0.42) circle (1.0pt);
    \draw[#3!65!black, line width=0.35pt] (0.32, 0.36) -- (0.50, 0.02) -- (0.22, -0.12) -- (0.38, -0.42);
    % Trans-callosal bridge
    \draw[#3!60!black, line width=0.35pt, dashed] (-0.22, -0.12) -- (0.22, -0.12);
  \end{scope}
}

% Graph Icon: #1 = position, #2 = scale, #3 = color
\def\drawgraphicon#1#2#3{
  \begin{scope}[shift={(#1)}, scale=#2]
    \draw[fill=#3!15, draw=#3!80!black, rounded corners=1.5pt, line width=0.55pt] (-0.6,-0.45) rectangle (0.6,0.45);
    \fill[orange!90!black] (-0.32, 0.16) circle (1.2pt);
    \fill[blue!90!black] (0.32, 0.16) circle (1.2pt);
    \fill[green!80!black] (0, -0.22) circle (1.2pt);
    \draw[gray!70!black, line width=0.4pt] (-0.32, 0.16) -- (0.32, 0.16) -- (0, -0.22) -- cycle;
  \end{scope}
}

% Database/Search Icon: #1 = position, #2 = scale, #3 = color
\def\drawdbicon#1#2#3{
  \begin{scope}[shift={(#1)}, scale=#2]
    \draw[fill=#3!15, draw=#3!80!black, line width=0.55pt] (0,0.3) ellipse (0.55 and 0.18);
    \draw[fill=#3!15, draw=#3!80!black, line width=0.55pt] (-0.55,0.3) -- (-0.55,-0.3) arc (180:360:0.55 and 0.18) -- (0.55,0.3);
    \draw[#3!80!black, line width=0.45pt] (-0.55,0) arc (180:360:0.55 and 0.18);
  \end{scope}
}

% ==========================================================
% GEOMETRY:
% Total diagram width: 12.8cm
% Column 1 (Left - Tier 1):  X Center = 3.1cm, Width = 6.0cm
% Column 2 (Right - Tier 2): X Center = 9.7cm, Width = 6.0cm
% Gap between columns: 0.6cm
% Column Height: 6.8cm (Y from 3.4 to -3.4)
% ==========================================================

% ----------------------------------------------------------
% COLUMN 1: TIER 1 (PRIMARY EVIDENCE EVALUATION & CLARITY AUDIT)
% ----------------------------------------------------------
\node[tier_col=blue, minimum width=6.1cm, minimum height=6.8cm] (col1) at (3.15, 0) {};
\node[col_header=blue, minimum width=5.8cm, anchor=north] (t1) at ([yshift=-1.8mm]col1.north) {
  \textbf{Tier 1: Initial Evidence Reasoning \& Clarity Audit}
};

% Step 1.1: Input Block
\node[alg_io=blue, text width=5.3cm] (b1_in) at (3.15, 2.35) {
  \drawgraphicon{-2.3, 0}{0.55}{blue}
  \hspace*{7mm}\textbf{Step 1: Evidence Multigraph + Guided Scaffold}\\
  {\fontsize{4.8pt}{5.6pt}\selectfont
  $\bullet$ Complete unpruned graph $G_q$ with linear traversal scaffolding $P_q$\\
  $\bullet$ \textbf{Running Example:} Question asks university of club formed in 1989\\
  $\bullet$ \textcolor{blue!90!black}{\textbf{Tied Candidates:}} \texttt{Toronto Eagles (1989)} vs \texttt{Toronto Blues (1989)}}
};

% Step 1.2: Process Block (Primary LLM Call with Brain Icon)
\node[alg_proc=purple, text width=5.3cm] (b1_llm) at (3.15, 0.95) {
  \drawbrain{-2.3, 0}{0.48}{purple}
  \hspace*{7mm}\textbf{Step 2: Primary LLM Evaluation (Call 1)}\\
  {\fontsize{4.8pt}{5.6pt}\selectfont
  $\bullet$ Evaluates initial evidence graph along guided traversal path\\
  $\bullet$ \textcolor{purple!90!black}{\textbf{Strict Audit Rule:}} Zero guessing on ambiguous candidates}
};
\draw[flow_blue] (b1_in) -- (b1_llm);

% Step 1.3: Decision Diamond
\node[alg_decision=purple, text width=2.4cm] (b1_dec) at (3.15, -0.55) {
  Clarity Audit:\\
  Unambiguous?
};
\draw[flow] (b1_llm) -- (b1_dec);

% Branch 1: Yes -> Fast Exit (Right exit pill inside Col 1)
\draw[flow_green] (b1_dec.east) -- ++(0.4, 0) |- (b1_exit.west);
\node[alg_exit, text width=1.65cm] (b1_exit) at (4.95, -1.45) {
  \textbf{Fast Exit}\\[-0.2mm]
  {\fontsize{4.4pt}{5.0pt}\selectfont $\approx 80\%$ Queries\\1 LLM Call $\to$ Answer}
};
\node[font=\bfseries\tiny, text=green!75!black, anchor=south west] at (b1_dec.east) {Yes};

% Branch 2: No -> Diagnostic Handoff
\node[font=\bfseries\tiny, text=orange!85!black, anchor=east] at ([xshift=-1mm]b1_dec.south) {No (Tied)};
\node[alg_proc=orange, fill=orange!4, draw=orange!75!black, text width=3.4cm] (b1_handoff) at (2.05, -2.45) {
  \textbf{Step 3: Diagnostic Handoff $\mathcal{D}$}\\
  {\fontsize{4.7pt}{5.5pt}\selectfont
  $\bullet$ Collision on \texttt{formed = 1989}\\
  $\bullet$ Missing \texttt{Blues} text bridge passage\\
  $\bullet$ Emits structured diagnostic packet $\mathcal{D}$}
};
\draw[flow_orange] (b1_dec.south) |- (b1_handoff.north);

% ----------------------------------------------------------
% CONNECTOR ARROW: TIER 1 HANDOFF -> TIER 2 BRIDGE
% ----------------------------------------------------------
\draw[handoff_wire] (b1_handoff.east) -- (6.75, -2.45) -- (6.75, 2.35) -- (col2_in.west);
\node[fill=orange!12, draw=orange!70!black, line width=0.4pt, rounded corners=2pt, inner sep=1.4pt, font=\fontsize{4.5pt}{5.2pt}\selectfont\bfseries, text=orange!95!black, rotate=90] at (6.45, 0) {
  Diagnostic Handoff (Collision Alert)
};

% ----------------------------------------------------------
% COLUMN 2: TIER 2 (TARGETED COLLISION RESOLUTION)
% ----------------------------------------------------------
\node[tier_col=teal, minimum width=6.1cm, minimum height=6.8cm] (col2) at (9.85, 0) {};
\node[col_header=teal, minimum width=5.8cm, anchor=north] (t2) at ([yshift=-1.8mm]col2.north) {
  \textbf{Tier 2: Targeted Collision Resolution \& Verification}
};

% Step 2.1: Automated Bridge Search & State Capsule (Zero LLM)
\node[alg_io=teal, text width=5.3cm] (col2_in) at (9.85, 2.35) {
  \drawdbicon{-2.3, 0}{0.55}{teal}
  \hspace*{7mm}\textbf{Step 1: Automated Bridge Search (Zero LLM)}\\
  {\fontsize{4.8pt}{5.6pt}\selectfont
  $\bullet$ Queries text index for missing bridge doc: \texttt{Doc:Toronto\_Blues}\\
  $\bullet$ Discards all irrelevant rows $\to$ builds \textbf{Minimal State Capsule $\mathcal{S}_{\text{min}}$}\\
  $\bullet$ \textcolor{teal!90!black}{\textbf{Isolated Context:}} Strictly tied candidates + bridge evidence}
};

% Step 2.2: Process Block (Targeted LLM Call with Brain Icon)
\node[alg_proc=purple, text width=5.3cm] (col2_llm) at (9.85, 0.95) {
  \drawbrain{-2.3, 0}{0.48}{purple}
  \hspace*{7mm}\textbf{Step 2: Targeted LLM Resolution (Call 2)}\\
  {\fontsize{4.8pt}{5.6pt}\selectfont
  $\bullet$ Evaluates isolated tied candidates directly against bridge passage\\
  $\bullet$ \textcolor{purple!90!black}{\textbf{Zero Noise:}} Eliminates context dilution for crisp resolution}
};
\draw[flow_teal] (col2_in) -- (col2_llm);

% Step 2.3: Decision Diamond
\node[alg_decision=teal, text width=2.4cm] (col2_dec) at (9.85, -0.55) {
  Fact Grounded in\\
  Bridge Evidence?
};
\draw[flow] (col2_llm) -- (col2_dec);

% Step 2.4: Final Verified Output
\node[alg_exit, text width=4.9cm, fill=green!15, draw=green!75!black] (col2_final) at (9.85, -2.45) {
  \textbf{Step 3: Final Verified Answer: ``York''}\\[0.4mm]
  {\fontsize{4.8pt}{5.6pt}\selectfont
  $\le 2$ LLM Calls Total $\bullet$ 100\% Grounded Provenance $\bullet$ Zero Hallucination}
};
\draw[flow_green] (col2_dec.south) -- (col2_final.north);
\node[font=\bfseries\tiny, text=green!75!black, anchor=east] at ([xshift=-1mm]col2_dec.south) {Yes (Verified)};

\end{tikzpicture}
\end{document}
"""

with open("/workspace/kiennt/online-kg-rag/paper_v2/figures/generate_fig3_parallel_v2.tex", "w") as f:
    f.write(latex_content)

cmd = "pdflatex -interaction=nonstopmode generate_fig3_parallel_v2.tex && pdftoppm -png -r 150 generate_fig3_parallel_v2.pdf fig3_par_v2_out"
res = subprocess.run(cmd, shell=True, cwd="/workspace/kiennt/online-kg-rag/paper_v2/figures", capture_output=True, text=True)
print("Return code:", res.returncode)
