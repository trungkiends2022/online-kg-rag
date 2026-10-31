import subprocess

latex_content = r"""\documentclass[tikz,border=2mm]{standalone}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,positioning,shapes.geometric,fit,backgrounds,calc}
\usepackage{lmodern}

\begin{document}
\begin{tikzpicture}[
  >=Latex,
  font=\sffamily\scriptsize,
  % Panels
  tier_panel/.style={draw=#1!60!black, fill=#1!2!white, rounded corners=5pt, line width=0.65pt},
  title_badge/.style={fill=#1!12, draw=#1!60!black, line width=0.45pt, rounded corners=2.5pt, font=\bfseries\scriptsize, text=#1!90!black, inner sep=2pt},
  % Actor cards
  actor_card/.style={draw=#1!75!black, fill=#1!8, rounded corners=4pt, line width=0.65pt, inner sep=2.5pt},
  % Message capsules
  packet_box/.style={draw=gray!30, fill=white, rounded corners=3pt, line width=0.45pt, inner sep=3pt},
  msg_label/.style={fill=#1!14, draw=#1!75!black, line width=0.4pt, rounded corners=2pt, inner sep=1.2pt, font=\bfseries\tiny, text=#1!95!black},
  % Exits
  exit_box/.style={draw=green!65!black, fill=green!10, rounded corners=3pt, line width=0.65pt, inner sep=2.5pt, align=center},
  % Arrows
  fwd_arrow/.style={->, line width=1.05pt, draw=blue!75!black},
  ret_arrow/.style={->, line width=1.05pt, draw=orange!85!black},
  succ_arrow/.style={->, line width=1.1pt, draw=green!65!black},
  step_arrow/.style={->, line width=0.85pt, draw=gray!65!black, dashed}
]

% ==========================================================
% ICON MACROS
% ==========================================================

% Brain Icon (x, y, scale, color)
\def\drawbrain#1#2#3#4{
  \begin{scope}[shift={(#1)}, scale=#3]
    % Left hemisphere
    \draw[fill=#4!18, draw=#4!85!black, line width=0.7pt]
      (0, 0.72) 
      .. controls (-0.35, 0.82) and (-0.72, 0.62) .. (-0.72, 0.28)
      .. controls (-0.92, 0.12) and (-0.92, -0.22) .. (-0.68, -0.34)
      .. controls (-0.76, -0.58) and (-0.52, -0.78) .. (-0.28, -0.68)
      .. controls (-0.18, -0.82) and (-0.05, -0.68) .. (0, -0.58)
      -- cycle;
    % Right hemisphere
    \draw[fill=#4!18, draw=#4!85!black, line width=0.7pt]
      (0, 0.72) 
      .. controls (0.35, 0.82) and (0.72, 0.62) .. (0.72, 0.28)
      .. controls (0.92, 0.12) and (0.92, -0.22) .. (0.68, -0.34)
      .. controls (0.76, -0.58) and (0.52, -0.78) .. (0.28, -0.68)
      .. controls (0.18, -0.82) and (0.05, -0.68) .. (0, -0.58)
      -- cycle;
    % Midline
    \draw[#4!85!black, line width=0.7pt] (0, 0.70) -- (0, -0.56);
    % Neural nodes & synapses (Left)
    \fill[#4!85!black] (-0.32, 0.36) circle (1.1pt);
    \fill[#4!85!black] (-0.50, 0.02) circle (1.1pt);
    \fill[#4!85!black] (-0.22, -0.12) circle (1.1pt);
    \fill[#4!85!black] (-0.38, -0.42) circle (1.1pt);
    \draw[#4!65!black, line width=0.4pt] (-0.32, 0.36) -- (-0.50, 0.02) -- (-0.22, -0.12) -- (-0.38, -0.42);
    \draw[#4!65!black, line width=0.4pt] (-0.32, 0.36) -- (-0.22, -0.12);
    % Neural nodes & synapses (Right)
    \fill[#4!85!black] (0.32, 0.36) circle (1.1pt);
    \fill[#4!85!black] (0.50, 0.02) circle (1.1pt);
    \fill[#4!85!black] (0.22, -0.12) circle (1.1pt);
    \fill[#4!85!black] (0.38, -0.42) circle (1.1pt);
    \draw[#4!65!black, line width=0.4pt] (0.32, 0.36) -- (0.50, 0.02) -- (0.22, -0.12) -- (0.38, -0.42);
    \draw[#4!65!black, line width=0.4pt] (0.32, 0.36) -- (0.22, -0.12);
    % Synaptic bridge
    \draw[#4!60!black, line width=0.4pt, dashed] (-0.22, -0.12) -- (0.22, -0.12);
  \end{scope}
}

% Graph/System Icon Macro (x, y, scale, color)
\def\drawkgicon#1#2#3#4{
  \begin{scope}[shift={(#1)}, scale=#3]
    \draw[fill=#4!18, draw=#4!85!black, rounded corners=2pt, line width=0.65pt] (-0.65,-0.55) rectangle (0.65,0.55);
    \fill[orange!90!black] (-0.35, 0.22) circle (1.4pt);
    \fill[blue!90!black] (0.35, 0.22) circle (1.4pt);
    \fill[green!80!black] (0, -0.28) circle (1.4pt);
    \draw[gray!75!black, line width=0.45pt] (-0.35, 0.22) -- (0.35, 0.22) -- (0, -0.28) -- cycle;
  \end{scope}
}

% ==========================================================
% GEOMETRY SETUP
% Total width: 12.8cm, Center: 6.4cm
% Actor 1 (Left): X = 1.45cm (width = 2.3cm)
% Actor 2 (Right): X = 11.35cm (width = 2.3cm)
% Interaction Area: X = 2.7cm to 10.1cm (width = 7.4cm)
% ==========================================================

% ==========================================================
% TIER 1 PANEL: INITIAL REASONING & CLARITY AUDIT
% ==========================================================
\node[tier_panel=blue, minimum width=12.8cm, minimum height=3.75cm] (p1) at (6.4, 4.05) {};
\node[title_badge=blue, anchor=north] at (6.4, 5.85) {Tier 1: Primary Evidence Evaluation \& Structural Clarity Check};

% Left Actor (QEG-RAG)
\node[actor_card=blue, minimum width=2.3cm, minimum height=2.85cm] (qeg1) at (1.45, 3.9) {};
\drawkgicon{1.45, 4.75}{0.65}{blue};
\node[font=\bfseries\scriptsize, text=blue!90!black] at (1.45, 4.22) {QEG-RAG Engine};
\node[font=\fontsize{4.8pt}{5.6pt}\selectfont, text=gray!80!black, align=center] at (1.45, 3.55) {
  \textbf{Retrieval Controller}\\[0.6mm]
  $\bullet$ Evidence graph $G_q$\\
  $\bullet$ Guided path $P_q$\\[0.6mm]
  \textcolor{blue!85!black}{\textbf{Context: Unpruned}}
};

% Right Actor (LLM Reasoner with Brain Icon)
\node[actor_card=purple, minimum width=2.3cm, minimum height=2.85cm] (llm1) at (11.35, 3.9) {};
\drawbrain{11.35, 4.75}{0.65}{purple};
\node[font=\bfseries\scriptsize, text=purple!90!black] at (11.35, 4.22) {Backbone LLM};
\node[font=\fontsize{4.8pt}{5.6pt}\selectfont, text=gray!80!black, align=center] at (11.35, 3.55) {
  \textbf{Neural Reasoner}\\[0.6mm]
  $\bullet$ Evaluates evidence\\
  $\bullet$ Clarity verification\\[0.6mm]
  \textcolor{purple!85!black}{\textbf{Strict Audit Mode}}
};

% --- Turn 1: Request Arrow (QEG-RAG -> LLM) ---
\draw[fwd_arrow] (2.65, 4.7) -- (10.15, 4.7);
\node[msg_label=blue, anchor=south] at (6.4, 4.72) {Step 1 (Call 1): Send Evidence Graph + Guided Path Scaffold};

% Packet 1 (Turn 1 Data)
\node[packet_box, text width=7.0cm, align=left] at (6.4, 4.12) {
  {\fontsize{5.0pt}{5.9pt}\selectfont
  $\bullet$ Linearized multigraph traversal path over table rows and text passages\\
  $\bullet$ \textbf{Running Example:} Question asks which university is affiliated with club formed in 1989\\
  $\bullet$ \textcolor{blue!90!black}{\textbf{Candidates Encountered:}} \texttt{Toronto Eagles (1989)} vs \texttt{Toronto Blues (1989)}}
};

% --- Turn 1: Outcomes ---
% Outcome A: Fast Exit (Right exit arrow)
\draw[succ_arrow] (11.35, 2.45) -- (11.35, 2.05);
\node[exit_box, text width=2.4cm, anchor=north] at (11.35, 2.1) {
  \textbf{Fast Exit ($\approx 80\%$)}\\[-0.2mm]
  {\fontsize{4.6pt}{5.4pt}\selectfont 1 Call $\to$ Verified Answer}
};

% Outcome B: Collision Detected -> Diagnostic Handoff (Return Arrow to QEG-RAG)
\draw[ret_arrow] (10.15, 2.85) -- (2.65, 2.85);
\node[msg_label=orange, anchor=south] at (6.4, 2.87) {Step 2: Diagnostic Handoff (Collision Alert \& Missing Link)};

% Packet 2 (Handoff Payload)
\node[packet_box, draw=orange!45, fill=orange!3, text width=7.0cm, align=left] at (6.4, 2.3) {
  {\fontsize{5.0pt}{5.9pt}\selectfont
  $\bullet$ \textcolor{orange!90!black}{\textbf{Decision:}} Both clubs match \texttt{formed = 1989}; text bridge for \texttt{Blues} is missing\\
  $\bullet$ Emits structured diagnostic packet $\mathcal{D}$: identifies competing rows and pauses without guessing}
};

% ==========================================================
% BRIDGE PHASE: ZERO-LLM TARGETED RETRIEVAL
% ==========================================================
\node[tier_panel=gray, fill=gray!6, draw=gray!40, minimum width=12.8cm, minimum height=1.1cm] (p_mid) at (6.4, 0.95) {};
\node[title_badge=gray!80!black, anchor=west] at (0.2, 1.35) {Automated Bridge Search (Zero LLM Calls $\bullet$ Purely Algorithmic)};

\node[text width=12.2cm, align=left] at (6.4, 0.88) {
  \begin{minipage}{0.31\linewidth}
    \textcolor{blue!90!black}{\textbf{1. Intercept Handoff:}}\\
    {\fontsize{4.9pt}{5.7pt}\selectfont Parse competing entities: \texttt{Toronto Eagles} vs \texttt{Blues}}
  \end{minipage}
  \hfill
  \begin{minipage}{0.34\linewidth}
    \textcolor{orange!90!black}{\textbf{2. Targeted Search (0 LLM):}}\\
    {\fontsize{4.9pt}{5.7pt}\selectfont Query passage index $\to$ retrieve \texttt{Doc:Toronto\_Blues}}
  \end{minipage}
  \hfill
  \begin{minipage}{0.31\linewidth}
    \textcolor{teal!90!black}{\textbf{3. Assemble State Capsule:}}\\
    {\fontsize{4.9pt}{5.7pt}\selectfont Prune non-tied rows $\to$ build capsule $\mathcal{S}_{\text{min}}$}
  \end{minipage}
};

% Vertical sequence connectors on QEG-RAG side
\draw[step_arrow] (1.45, 2.45) -- (1.45, 1.55);
\draw[step_arrow] (1.45, 0.35) -- (1.45, -0.45);

% ==========================================================
% TIER 2 PANEL: TARGETED RESOLUTION & GROUNDING
% ==========================================================
\node[tier_panel=teal, fill=teal!2!white, minimum width=12.8cm, minimum height=2.45cm] (p2) at (6.4, -1.75) {};
\node[title_badge=teal!80!black, anchor=north] at (6.4, -0.55) {Tier 2: Targeted Collision Resolution \& Provenance Verification};

% Left Actor (Tier 2 QEG-RAG)
\node[actor_card=teal, minimum width=2.3cm, minimum height=1.75cm] (qeg2) at (1.45, -1.8) {};
\drawkgicon{1.45, -1.25}{0.55}{teal};
\node[font=\bfseries\scriptsize, text=teal!90!black] at (1.45, -1.62) {QEG-RAG};
\node[font=\fontsize{4.8pt}{5.6pt}\selectfont, text=gray!80!black, align=center] at (1.45, -2.1) {
  \textbf{Minimal Capsule}\\
  Tied rows + bridge doc
};

% Right Actor (Tier 2 LLM Reasoner with Brain Icon)
\node[actor_card=purple, minimum width=2.3cm, minimum height=1.75cm] (llm2) at (11.35, -1.8) {};
\drawbrain{11.35, -1.25}{0.55}{purple};
\node[font=\bfseries\scriptsize, text=purple!90!black] at (11.35, -1.62) {Backbone LLM};
\node[font=\fontsize{4.8pt}{5.6pt}\selectfont, text=gray!80!black, align=center] at (11.35, -2.1) {
  \textbf{Final Resolution}\\
  $\le 2$ LLM calls total
};

% --- Turn 2: Request Arrow (QEG-RAG -> LLM) ---
\draw[fwd_arrow, draw=teal!80!black] (2.65, -1.25) -- (10.15, -1.25);
\node[msg_label=teal, anchor=south] at (6.4, -1.23) {Step 3 (Call 2): Send Minimal State Capsule $\mathcal{S}_{\text{min}}$};

% Packet 3 (Turn 2 Data)
\node[packet_box, draw=teal!45, fill=teal!3, text width=7.0cm, align=left] at (6.4, -1.8) {
  {\fontsize{5.0pt}{5.9pt}\selectfont
  $\bullet$ Isolated context: contains strictly tied candidate rows and fetched bridge text\\
  $\bullet$ Complete absence of noise eliminates context dilution and enables crisp resolution\\
  $\bullet$ Factual evidence in \texttt{Doc:Toronto\_Blues} identifies \texttt{York University}}
};

% --- Turn 2: Final Verified Resolution Arrow ---
\draw[succ_arrow] (11.35, -2.7) -- (11.35, -3.05);
\node[exit_box, text width=2.5cm, anchor=north] at (11.35, -3.1) {
  \textbf{Verified Answer: ``York''}\\[-0.2mm]
  {\fontsize{4.6pt}{5.4pt}\selectfont Grounded by Evidence $\bullet$ Full Provenance}
};

\end{tikzpicture}
\end{document}
"""

with open("/workspace/kiennt/online-kg-rag/paper_v2/figures/generate_fig3_perfect.tex", "w") as f:
    f.write(latex_content)

cmd = "pdflatex -interaction=nonstopmode generate_fig3_perfect.tex && pdftoppm -png -r 150 generate_fig3_perfect.pdf fig3_perfect_out"
res = subprocess.run(cmd, shell=True, cwd="/workspace/kiennt/online-kg-rag/paper_v2/figures", capture_output=True, text=True)
print("Return code:", res.returncode)
