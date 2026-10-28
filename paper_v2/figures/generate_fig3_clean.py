import os

tex_code = r"""\begin{tikzpicture}[
  >=Latex,
  font=\scriptsize,
  panel/.style={draw=#1!75!black, fill=#1!3, rounded corners=6pt, line width=0.7pt},
  titlebar/.style={fill=#1!18, draw=#1!75!black, line width=0.5pt, rounded corners=3pt, font=\bfseries\scriptsize, text=#1!90!black, align=center, inner sep=3pt, minimum height=4.6mm},
  box/.style={draw=gray!40, fill=white, rounded corners=3pt, line width=0.45pt, inner sep=4pt},
  llmbox/.style={draw=#1!80!black, fill=#1!12, rounded corners=4pt, line width=0.65pt, inner sep=4.5pt},
  badge/.style={fill=white, draw=#1!75!black, line width=0.5pt, rounded corners=2.5pt, inner sep=2.5pt, font=\tiny\bfseries, text=#1!90!black},
  flow/.style={->, line width=0.85pt, draw=gray!70!black},
  flow_orange/.style={->, line width=0.9pt, draw=orange!85!black},
  flow_purple/.style={->, line width=0.9pt, draw=purple!85!black},
  flow_teal/.style={->, line width=0.9pt, draw=teal!85!black},
  flow_green/.style={->, line width=0.95pt, draw=green!60!black}
]

% Panel dimensions:
% Center X: 2.7, 8.8, 14.9 (width 5.2cm each, gaps 0.9cm)
% Center Y: -0.32, Height: 10.2cm (Top: +4.78cm, Bottom: -5.42cm)

% ========================================================
% COLUMN 1: TIER 1 (L1 READER & AUDIT PROTOCOL)
% ========================================================
\node[panel=orange, minimum width=5.2cm, minimum height=10.2cm] (p_l1) at (2.70, -0.32) {};
\node[titlebar=orange, text width=4.8cm, anchor=north] (t_l1) at ([yshift=-2.8mm]p_l1.north) {Tier 1: L1 Reader \& Controlled Audit};

\node[box, text width=4.75cm, fill=orange!6, draw=orange!45, anchor=north] (l1_in) at ([yshift=-2.9mm]t_l1.south) {
  \textbf{Input Context to L1 LLM ($\mathcal{X}_{\text{L1}}$)} \\[0.3mm]
  \tiny $\bullet$ Complete multigraph $\mathcal{X}^*(G_q)$ (lossless compression) \\
  $\bullet$ Scored path guide $p_1$ ($S=7.85$) as attention steer \\
  $\bullet$ Non-filtering: preserves full topological evidence
};

\node[llmbox=orange, text width=4.75cm, anchor=north] (l1_llm) at ([yshift=-2.9mm]l1_in.south) {
  \textbf{Backbone LLM (Call 1): Collision Audit} \\[0.3mm]
  \tiny Evaluates candidate collision set $\mathcal{C}_q = \{\rho_0, \rho_1\}$: \\
  $\bullet$ \textbf{Decision Rule}: Branch on structural determinacy \\
  $\bullet$ Strictly prohibits ungrounded parametric guessing
};

% Branching Split: Branch A (Determined) vs Branch B (Under-determined)
\node[box, text width=2.15cm, fill=green!12, draw=green!65!black, line width=0.55pt, anchor=north west] (l1_branch_a) at ([yshift=-2.9mm, xshift=0.5mm]l1_llm.south west) {
  \textbf{Branch A ($|\mathcal{C}_q|=1$)} \\[0.2mm]
  \tiny $\bullet$ Single path found \\
  $\bullet$ \textbf{L1 Fast Exit}: verified $a^*$ \\
  $\bullet$ 1 call, terminates here
};

\node[box, text width=2.15cm, fill=orange!14, draw=orange!75!black, line width=0.55pt, anchor=north east] (l1_branch_b) at ([yshift=-2.9mm, xshift=-0.5mm]l1_llm.south east) {
  \textbf{Branch B ($|\mathcal{C}_q|>1$)} \\[0.2mm]
  \tiny $\bullet$ Collision detected \\
  $\bullet$ Defers guessing \\
  $\bullet$ Emits handoff $\mathcal{H}_{\text{diag}}$
};

\node[box, text width=4.75cm, fill=orange!18, draw=orange!85!black, line width=0.55pt, anchor=north] (l1_diag) at ([yshift=-2.9mm]l1_branch_b.south -| l1_llm.south) {
  \textbf{Structured Diagnostic Emission $\mathcal{H}_{\text{diag}}$} \\[0.3mm]
  \fontsize{4.6pt}{5.6pt}\selectfont
  \texttt{\{"candidates": ["$\rho_0$", "$\rho_1$"], "blocker": "missing\_link",\\
  \ "needed\_check": "check town name in passage"\}}
};

\draw[flow_orange] (l1_in.south) -- (l1_llm.north);
\draw[flow_green] (l1_llm.south -| l1_branch_a.north) -- (l1_branch_a.north);
\draw[flow_orange] (l1_llm.south -| l1_branch_b.north) -- (l1_branch_b.north);
\draw[flow_orange] (l1_branch_b.south) -- (l1_diag.north -| l1_branch_b.south);

% ========================================================
% COLUMN 2: CONTROLLER & TARGETED RETRIEVAL AUGMENTATION
% ========================================================
\node[panel=purple, minimum width=5.2cm, minimum height=10.2cm] (p_ret) at (8.80, -0.32) {};
\node[titlebar=purple, text width=4.8cm, anchor=north] (t_ret) at ([yshift=-2.8mm]p_ret.north) {Targeted Evidence Retrieval\\[-0.2mm]\fontsize{5.5pt}{6.5pt}\selectfont (Controller Augmentation)};

\node[box, text width=4.75cm, fill=purple!8, draw=purple!45, anchor=north] (ret_sym) at ([yshift=-2.8mm]t_ret.south) {
  \textbf{Symmetric Candidate Expansion ($\mathcal{R}_{\text{target}}$)} \\[0.3mm]
  \tiny $\bullet$ Focus candidates from handoff: $\mathcal{C}_{\text{focus}} = \{\rho_0, \rho_1\}$ \\
  $\bullet$ Query Wikipedia hyperlink cache per candidate \\
  $\bullet$ Bounded budget: $k_{\text{focus}} = 2$ passages / row
};

\node[box, text width=4.75cm, fill=purple!15, draw=purple!75!black, line width=0.5pt, anchor=north] (ret_delta) at ([yshift=-2.8mm]ret_sym.south) {
  \textbf{Targeted Delta Evidence Cards ($\Delta \mathcal{D}$)} \\[0.3mm]
  \tiny $\bullet$ Row $\rho_0$: \texttt{Doc:Toronto} $\to$ \textit{``...town of York (1793)...''} \\
  $\bullet$ Row $\rho_1$: \texttt{Doc:Hamilton} $\to$ \textit{``...founded in 1816...''} \\
  $\bullet$ Symmetric balance prevents candidate bias
};

\node[box, text width=4.75cm, fill=teal!10, draw=teal!60, anchor=north] (capsule_pack) at ([yshift=-2.8mm]ret_delta.south) {
  \textbf{Packager: State Capsule $\mathcal{K}_{\text{L2}}$} \\[0.3mm]
  \tiny Integrates focus row bindings $+$ delta passages $\Delta \mathcal{D}$ \\
  $\mathcal{K}_{\text{L2}} = (q, \, \psi_{\text{check}}, \, \{\mathcal{G}^*(\rho_c)\}_{c \in \mathcal{C}_{\text{focus}}}, \, \Delta \mathcal{D})$
};

\node[box, text width=4.75cm, fill=purple!6, draw=purple!40, anchor=north] (ret_prop) at ([yshift=-2.8mm]capsule_pack.south) {
  \textbf{Sufficiency Guarantee (Prop.~2)} \\[0.3mm]
  \tiny $\bullet$ Zero informational loss: $I(a^*; \mathcal{X}_{\text{L1}} \cup \Delta \mathcal{D} \mid \mathcal{K}_{\text{L2}}) = 0$ \\
  $\bullet$ Bounded context: eliminates irrelevant clutter \\
  $\bullet$ Ready for factual disambiguation at Tier 2
};

\draw[flow_purple] (ret_sym.south) -- (ret_delta.north);
\draw[flow_teal] (ret_delta.south) -- (capsule_pack.north);
\draw[flow_purple] (capsule_pack.south) -- (ret_prop.north);

% ========================================================
% COLUMN 3: TIER 2 (L2 READER & GROUNDED RESOLUTION)
% ========================================================
\node[panel=teal, minimum width=5.2cm, minimum height=10.2cm] (p_l2) at (14.90, -0.32) {};
\node[titlebar=teal, text width=4.8cm, anchor=north] (t_l2) at ([yshift=-2.8mm]p_l2.north) {Tier 2: L2 Reader (Second LLM Call)};

\node[box, text width=4.75cm, fill=teal!6, draw=teal!45, anchor=north] (l2_capsule) at ([yshift=-4.8mm]t_l2.south) {
  \textbf{Minimal Sufficient State Capsule $\mathcal{K}_{\text{L2}}$} \\[0.3mm]
  \fontsize{4.6pt}{5.6pt}\selectfont
  \texttt{\{"question": "city with club formed in 1989",\\
  \ "unresolved": "needed\_check: town name",\\
  \ "focus\_bindings": [\\
  \ \ \{"rec": "$\rho_0$", "club": "Eagles", "yr": 1989\},\\
  \ \ \{"rec": "$\rho_1$", "club": "Tigers", "yr": 1991\}\\
  \ ],\\
  \ "delta\_evidence": [\\
  \ \ \{"target": "$\rho_0$", "doc": "town of York (1793)"\},\\
  \ \ \{"target": "$\rho_1$", "doc": "founded in 1816"\}\\
  \ ]\}}
};

\node[llmbox=teal, text width=4.75cm, inner sep=5.0pt, anchor=north] (l2_llm) at ([yshift=-4.8mm]l2_capsule.south) {
  \textbf{Backbone LLM (Call 2) -- Factual Reader} \\[0.3mm]
  \tiny $\bullet$ Evaluates grounded delta facts in $\mathcal{K}_{\text{L2}}$ at $T=0$ \\
  $\bullet$ Disambiguates tie between $\rho_0$ and $\rho_1$ factually \\
  $\bullet$ Eliminates heuristic lexical tiebreaking
};

\node[box, text width=4.75cm, fill=green!16, draw=green!60!black, line width=0.75pt, inner sep=5.0pt, anchor=north] (l2_res) at ([yshift=-4.8mm]l2_llm.south) {
  \textbf{Final Conclusive Resolution} \\[0.3mm]
  \tiny $\bullet$ \textbf{Verified Answer}: \texttt{"York"} \\
  $\bullet$ \textbf{Provenance Homomorphism} $\pi: a^* \rightarrow E_q^*$: \\
  \ \ $\rho_0 \text{ (row 0)} \xrightarrow{E_{\text{link}}} \text{Toronto} \xrightarrow{E_{\text{text}}} \text{York}$ \\
  $\bullet$ Validated against ground truth without hallucination
};

\draw[flow_teal] (l2_capsule.south) -- (l2_llm.north);
\draw[flow_teal] (l2_llm.south) -- (l2_res.north);

% ========================================================
% INTER-PANEL BRIDGING ARROWS (Rotated Vertical Labels)
% ========================================================
\coordinate (c1_turn) at (5.75, 0);
\draw[flow_orange] (l1_diag.east) -- (l1_diag.east -| c1_turn) 
  -- node[rotate=90, midway, badge=orange] {Diagnostic Handoff $\mathcal{H}_{\text{diag}}$} 
  (ret_sym.west -| c1_turn) -- (ret_sym.west);

\coordinate (c2_turn) at (11.85, 0);
\draw[flow_teal] (capsule_pack.east) -- (capsule_pack.east -| c2_turn) 
  -- node[rotate=90, midway, badge=teal] {State Capsule $\mathcal{K}_{\text{L2}}$} 
  (l2_capsule.west -| c2_turn) -- (l2_capsule.west);

\end{tikzpicture}
"""

with open("paper_v2/figures/diagnostic-l2-diagram.tex", "w") as f:
    f.write(tex_code)

print("Saved tuned diagnostic-l2-diagram.tex")
