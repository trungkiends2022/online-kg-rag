import subprocess

latex_content = r"""\documentclass[tikz,border=2mm]{standalone}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,positioning,shapes.geometric,fit,backgrounds,calc}
\usepackage{lmodern}

\begin{document}
\begin{tikzpicture}[
  >=Latex,
  font=\sffamily\scriptsize,
  % Global styles
  panel/.style={draw=#1!70!black, fill=#1!2!white, rounded corners=6pt, line width=0.7pt},
  panel_title/.style={fill=#1!12, draw=#1!60!black, line width=0.45pt, rounded corners=3pt, font=\bfseries\scriptsize, text=#1!95!black, inner sep=2.2pt},
  actor_box/.style={draw=#1!80!black, fill=#1!10, rounded corners=4pt, line width=0.7pt, inner sep=3pt},
  packet/.style={draw=#1!60!black, fill=white, rounded corners=3.5pt, line width=0.55pt, inner sep=3.5pt},
  badge/.style={fill=#1!15, draw=#1!75!black, line width=0.4pt, rounded corners=2pt, inner sep=1.2pt, font=\bfseries\tiny, text=#1!95!black},
  flow_fwd/.style={->, line width=1.1pt, draw=blue!75!black},
  flow_ret/.style={->, line width=1.1pt, draw=orange!85!black},
  flow_succ/.style={->, line width=1.2pt, draw=green!65!black},
  flow_proc/.style={->, line width=0.9pt, draw=gray!70!black, dashed}
]

% Brain Icon Macro (x, y, scale, color)
\def\drawbrain#1#2#3#4{
  \begin{scope}[shift={(#1)}, scale=#3]
    % Outer silhouette: Left hemisphere
    \draw[fill=#4!18, draw=#4!85!black, line width=0.75pt]
      (0, 0.72) 
      .. controls (-0.35, 0.82) and (-0.72, 0.62) .. (-0.72, 0.28)
      .. controls (-0.92, 0.12) and (-0.92, -0.22) .. (-0.68, -0.34)
      .. controls (-0.76, -0.58) and (-0.52, -0.78) .. (-0.28, -0.68)
      .. controls (-0.18, -0.82) and (-0.05, -0.68) .. (0, -0.58)
      -- cycle;
    % Right hemisphere
    \draw[fill=#4!18, draw=#4!85!black, line width=0.75pt]
      (0, 0.72) 
      .. controls (0.35, 0.82) and (0.72, 0.62) .. (0.72, 0.28)
      .. controls (0.92, 0.12) and (0.92, -0.22) .. (0.68, -0.34)
      .. controls (0.76, -0.58) and (0.52, -0.78) .. (0.28, -0.68)
      .. controls (0.18, -0.82) and (0.05, -0.68) .. (0, -0.58)
      -- cycle;
    % Midline
    \draw[#4!85!black, line width=0.75pt] (0, 0.70) -- (0, -0.56);
    % Neural network nodes and synapses (Left)
    \fill[#4!85!black] (-0.32, 0.36) circle (1.1pt);
    \fill[#4!85!black] (-0.50, 0.02) circle (1.1pt);
    \fill[#4!85!black] (-0.22, -0.12) circle (1.1pt);
    \fill[#4!85!black] (-0.38, -0.42) circle (1.1pt);
    \draw[#4!65!black, line width=0.45pt] (-0.32, 0.36) -- (-0.50, 0.02) -- (-0.22, -0.12) -- (-0.38, -0.42);
    \draw[#4!65!black, line width=0.45pt] (-0.32, 0.36) -- (-0.22, -0.12);
    % Neural network nodes and synapses (Right)
    \fill[#4!85!black] (0.32, 0.36) circle (1.1pt);
    \fill[#4!85!black] (0.50, 0.02) circle (1.1pt);
    \fill[#4!85!black] (0.22, -0.12) circle (1.1pt);
    \fill[#4!85!black] (0.38, -0.42) circle (1.1pt);
    \draw[#4!65!black, line width=0.45pt] (0.32, 0.36) -- (0.50, 0.02) -- (0.22, -0.12) -- (0.38, -0.42);
    \draw[#4!65!black, line width=0.45pt] (0.32, 0.36) -- (0.22, -0.12);
    % Trans-callosal bridge
    \draw[#4!60!black, line width=0.45pt, dashed] (-0.22, -0.12) -- (0.22, -0.12);
  \end{scope}
}

% Controller/Graph Icon Macro (x, y, scale, color)
\def\drawkgicon#1#2#3#4{
  \begin{scope}[shift={(#1)}, scale=#3]
    \draw[fill=#4!18, draw=#4!85!black, rounded corners=2pt, line width=0.7pt] (-0.6,-0.55) rectangle (0.6,0.55);
    \fill[orange!90!black] (-0.32, 0.22) circle (1.3pt);
    \fill[blue!90!black] (0.32, 0.22) circle (1.3pt);
    \fill[green!80!black] (0, -0.28) circle (1.3pt);
    \draw[gray!70!black, line width=0.45pt] (-0.32, 0.22) -- (0.32, 0.22) -- (0, -0.28) -- cycle;
  \end{scope}
}

% Total Width: 12.8cm, Center: 6.4cm
% Left Actor Center: 1.6cm, Right Actor Center: 11.2cm
% Communication Area: 3.2cm to 9.6cm

% ==========================================================
% TOP PANEL: TIER 1 INTERACTION
% ==========================================================
\node[panel=blue, minimum width=12.8cm, minimum height=3.65cm] (p1) at (6.4, 3.8) {};
\node[panel_title=blue, anchor=north] at (6.4, 5.5) {Tier 1: Primary Evidence Evaluation \& Structural Clarity Check};

% Left Actor (Tier 1): QEG-RAG Controller
\node[actor_box=blue, minimum width=2.5cm, minimum height=2.6cm] (qeg1) at (1.55, 3.65) {};
\drawkgicon{1.55, 4.45}{0.7}{blue};
\node[font=\bfseries\scriptsize, text=blue!90!black] at (1.55, 3.85) {QEG-RAG};
\node[font=\fontsize{5.0pt}{5.8pt}\selectfont, text=gray!80!black, align=center] at (1.55, 3.35) {
  Graph Engine\\
  \& Retrieval Controller\\[1mm]
  \textcolor{blue!85!black}{\textbf{Input Data:}}\\
  $\bullet$ Evidence graph $G_q$\\
  $\bullet$ Guided path $P_q$
};

% Right Actor (Tier 1): LLM Reasoner (Brain Icon)
\node[actor_box=purple, minimum width=2.5cm, minimum height=2.6cm] (llm1) at (11.25, 3.65) {};
\drawbrain{11.25, 4.45}{0.65}{purple};
\node[font=\bfseries\scriptsize, text=purple!90!black] at (11.25, 3.85) {LLM Reasoner};
\node[font=\fontsize{5.0pt}{5.8pt}\selectfont, text=gray!80!black, align=center] at (11.25, 3.35) {
  Neural Reasoner\\
  (Strict Audit Mode)\\[1mm]
  \textcolor{purple!85!black}{\textbf{Audit Rules:}}\\
  $\bullet$ Fast exit if clear\\
  $\bullet$ No guessing on ties
};

% Tier 1 Forward Arrow (Call 1 Request)
\draw[flow_fwd] (2.85, 4.35) -- (9.95, 4.35);
\node[badge=blue, anchor=south] at (6.4, 4.37) {1. Prompt (Call 1): Multigraph Evidence + Guided Path Scaffolding};

% Packet 1 (Call 1 Content)
\node[packet=blue, text width=6.2cm, align=left] at (6.4, 3.8) {
  {\fontsize{5.0pt}{6.0pt}\selectfont
  $\bullet$ Linearized traversal path along connected table rows \& text passages\\
  $\bullet$ \textbf{Running Example:} Question asks for university affiliated with club formed in 1989\\
  $\bullet$ Two candidate clubs match formed date: \texttt{Toronto Eagles} \& \texttt{Toronto Blues}}
};

% Tier 1 Exit / Return Arrows
% Case A: Fast Exit (Direct verified answer)
\draw[flow_succ] (11.25, 2.35) -- (12.7, 2.35);
\node[fill=green!12, draw=green!70!black, rounded corners=2.5pt, inner sep=2pt, font=\fontsize{4.8pt}{5.6pt}\selectfont\bfseries, text=green!85!black, text width=2.3cm, align=center] at (11.25, 2.65) {
  If unambiguous ($\approx 80\%$):\\
  \textcolor{green!70!black}{\textbf{Fast Exit}} (1 Call $\to$ Answer)
};

% Case B: Collision Detected -> Diagnostic Handoff (Return to QEG-RAG)
\draw[flow_ret] (9.95, 2.8) -- (2.85, 2.8);
\node[badge=orange, anchor=south] at (6.4, 2.82) {2. Diagnostic Handoff: Candidate Collision Alert};

% Packet 2 (Handoff Content)
\node[packet=orange, fill=orange!4, text width=6.2cm, align=left] at (6.4, 2.3) {
  {\fontsize{5.0pt}{6.0pt}\selectfont
  $\bullet$ \textcolor{orange!90!black}{\textbf{Clarity Audit:}} Attribute collision on \texttt{1989}; missing \texttt{Blues} bridge doc\\
  $\bullet$ Structured handoff emitted: tied candidates identified, execution paused without hallucination}
};

% ==========================================================
% MIDDLE BRIDGE: ZERO-LLM TARGETED RETRIEVAL
% ==========================================================
\node[panel=gray, fill=gray!7, draw=gray!40, minimum width=12.8cm, minimum height=1.15cm] (p_mid) at (6.4, 1.05) {};
\node[panel_title=gray!80!black, anchor=west] at (0.2, 1.45) {Automated Bridge Search (Zero LLM Calls $\bullet$ Deterministic)};

\node[text width=12.2cm, align=left] at (6.4, 0.95) {
  \begin{minipage}{0.31\linewidth}
    \textcolor{blue!90!black}{\textbf{1. Intercept Handoff:}}\\
    {\fontsize{5.0pt}{5.8pt}\selectfont Extract competing entities: \texttt{Toronto Eagles} vs \texttt{Blues}}
  \end{minipage}
  \hfill
  \begin{minipage}{0.34\linewidth}
    \textcolor{orange!90!black}{\textbf{2. Targeted Search (0 LLM):}}\\
    {\fontsize{5.0pt}{5.8pt}\selectfont Query passage store $\to$ retrieve missing \texttt{Doc:Toronto\_Blues}}
  \end{minipage}
  \hfill
  \begin{minipage}{0.31\linewidth}
    \textcolor{teal!90!black}{\textbf{3. Assemble State Capsule:}}\\
    {\fontsize{5.0pt}{5.8pt}\selectfont Prune irrelevant candidate rows $\to$ minimal context capsule $\mathcal{S}_{\text{min}}$}
  \end{minipage}
};

% Flow from Tier 1 QEG-RAG down to Bridge, and Bridge down to Tier 2 QEG-RAG
\draw[flow_proc] (1.55, 2.35) -- (1.55, 1.6);
\draw[flow_proc] (1.55, 0.5) -- (1.55, -0.2);

% ==========================================================
% BOTTOM PANEL: TIER 2 INTERACTION
% ==========================================================
\node[panel=teal, fill=teal!2!white, minimum width=12.8cm, minimum height=2.45cm] (p2) at (6.4, -1.45) {};
\node[panel_title=teal!80!black, anchor=north] at (6.4, -0.25) {Tier 2: Targeted Collision Resolution \& Provenance Verification};

% Left Actor (Tier 2): QEG-RAG Controller
\node[actor_box=teal, minimum width=2.5cm, minimum height=1.75cm] (qeg2) at (1.55, -1.5) {};
\drawkgicon{1.55, -1.0}{0.6}{teal};
\node[font=\bfseries\scriptsize, text=teal!90!black] at (1.55, -1.4) {QEG-RAG};
\node[font=\fontsize{5.0pt}{5.8pt}\selectfont, text=gray!80!black, align=center] at (1.55, -1.8) {
  State Capsule $\mathcal{S}_{\text{min}}$\\
  (Tied Rows + Bridge)
};

% Right Actor (Tier 2): LLM Reasoner (Brain Icon)
\node[actor_box=purple, minimum width=2.5cm, minimum height=1.75cm] (llm2) at (11.25, -1.5) {};
\drawbrain{11.25, -1.0}{0.6}{purple};
\node[font=\bfseries\scriptsize, text=purple!90!black] at (11.25, -1.4) {LLM Reasoner};
\node[font=\fontsize{5.0pt}{5.8pt}\selectfont, text=gray!80!black, align=center] at (11.25, -1.8) {
  Targeted Resolution\\
  (At most 2 calls total)
};

% Tier 2 Forward Arrow (Call 2 Request)
\draw[flow_fwd, draw=teal!80!black] (2.85, -1.0) -- (9.95, -1.0);
\node[badge=teal, anchor=south] at (6.4, -0.98) {3. Targeted Prompt (Call 2): Minimal State Capsule};

% Packet 3 (Call 2 Content)
\node[packet=teal, text width=6.2cm, align=left] at (6.4, -1.55) {
  {\fontsize{5.0pt}{6.0pt}\selectfont
  $\bullet$ Discards all irrelevant rows; contains strictly tied entities and targeted bridge evidence\\
  $\bullet$ Verified evidence shows: \texttt{Toronto Blues} affiliated with \texttt{York University}}
};

% Final Verified Resolution Arrow from LLM
\draw[flow_succ] (11.25, -2.4) -- (11.25, -2.6);
\node[fill=green!15, draw=green!75!black, rounded corners=3pt, line width=0.6pt, inner sep=2.5pt, font=\bfseries\scriptsize, text=green!90!black, anchor=north] at (11.25, -2.55) {
  \textbf{Final Verified Answer: ``York''}\\
  {\fontsize{4.8pt}{5.6pt}\selectfont Grounded by Facts $\bullet$ Full Provenance}
};

\end{tikzpicture}
\end{document}
"""

with open("/workspace/kiennt/online-kg-rag/paper_v2/figures/generate_fig3_refined.tex", "w") as f:
    f.write(latex_content)

cmd = "pdflatex -interaction=nonstopmode generate_fig3_refined.tex && pdftoppm -png -r 150 generate_fig3_refined.pdf fig3_refined_out"
res = subprocess.run(cmd, shell=True, cwd="/workspace/kiennt/online-kg-rag/paper_v2/figures", capture_output=True, text=True)
print("Return code:", res.returncode)
