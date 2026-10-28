fig2_xml = """<mxGraphModel dx="1400" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1420" pageHeight="640" background="#ffffff">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />

    <!-- Top Banner: Running Case Query -->
    <mxCell id="b_q" value="&lt;b style='font-size:13px;'&gt;Running Case (HybridQA):&lt;/b&gt; &lt;i style='font-size:12px;'&gt;&amp;quot;What was the original name of the city with an AFL club formed in 1989?&amp;quot;&lt;/i&gt;&lt;br&gt;&lt;span style='font-size:11px;'&gt;&lt;b&gt;Target Ground Truth:&lt;/b&gt; &lt;code style='background:#e8f8f5; color:#117864; font-weight:bold;'&gt;&amp;quot;York&amp;quot;&lt;/code&gt; &amp;nbsp;•&amp;nbsp; &lt;b&gt;Modality Fusion:&lt;/b&gt; Table (&lt;code&gt;AFL_Ontario_0&lt;/code&gt;) + Wikipedia Bridge (&lt;code&gt;/wiki/Toronto&lt;/code&gt;)&lt;/span&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ebf5fb;strokeColor=#2980b9;strokeWidth=1.5;align=left;spacingLeft=15;" vertex="1" parent="1">
      <mxGeometry x="30" y="20" width="1360" height="60" as="geometry" />
    </mxCell>

    <!-- ======================================================== -->
    <!-- STAGE 1: MULTI-SOURCE EVIDENCE INGESTION (Sec. 3.1) -->
    <!-- ======================================================== -->
    <mxCell id="p_s1" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8f9fa;strokeColor=#3498db;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="30" y="100" width="290" height="510" as="geometry" />
    </mxCell>
    <mxCell id="t_s1" value="&lt;b&gt;Stage 1 (Sec. 3.1): Multi-Source Ingestion&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d4e6f1;strokeColor=#3498db;fontSize=11;fontColor=#1b4f72;" vertex="1" parent="1">
      <mxGeometry x="45" y="115" width="260" height="32" as="geometry" />
    </mxCell>
    <mxCell id="b_s1_tbl" value="&lt;b&gt;Table T: &lt;code&gt;AFL_Ontario_0&lt;/code&gt;&lt;/b&gt;&lt;br&gt;&lt;table border='1' style='font-size:10px; width:100%; border-collapse:collapse; margin-top:3px;'&gt;&lt;tr style='background:#f2f4f4;'&gt;&lt;th&gt;Club&lt;/th&gt;&lt;th&gt;Formed&lt;/th&gt;&lt;th&gt;City&lt;/th&gt;&lt;/tr&gt;&lt;tr style='background:#d4e6f1; font-weight:bold;'&gt;&lt;td&gt;Tor. Eagles&lt;/td&gt;&lt;td&gt;1989&lt;/td&gt;&lt;td&gt;&lt;u&gt;Toronto&lt;/u&gt;&lt;/td&gt;&lt;/tr&gt;&lt;tr&gt;&lt;td&gt;Ham. Tigers&lt;/td&gt;&lt;td&gt;1991&lt;/td&gt;&lt;td&gt;Hamilton&lt;/td&gt;&lt;/tr&gt;&lt;/table&gt;&lt;div style='text-align:left; font-size:10px; margin-top:4px;'&gt;→ &lt;b&gt;Anchor Row 0&lt;/b&gt; (constraint: &lt;i&gt;1989&lt;/i&gt;)&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#bdc3c7;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="160" width="260" height="105" as="geometry" />
    </mxCell>
    <mxCell id="b_s1_doc" value="&lt;b&gt;Wikipedia Bridge Expansion&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px; line-height:1.3;'&gt;Traverse link: &lt;b&gt;Toronto&lt;/b&gt; → &lt;code&gt;Doc:Toronto&lt;/code&gt;&lt;br&gt;&lt;i&gt;&amp;quot;...capital of Ontario. Established in 1793 as town of &lt;b&gt;&lt;u&gt;York&lt;/u&gt;&lt;/b&gt;...&amp;quot;&lt;/i&gt;&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#bdc3c7;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="285" width="260" height="85" as="geometry" />
    </mxCell>
    <mxCell id="b_s1_out" value="&lt;b&gt;Retriever Output (k1=5, k2=3)&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Coarse candidate rows: {ρ0, ρ1, ...}&lt;br&gt;• Cell hyperlinks: &lt;code&gt;/wiki/Toronto&lt;/code&gt;&lt;br&gt;• 100% context preserved (0 doc pruning)&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ebf5fb;strokeColor=#2980b9;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="390" width="260" height="85" as="geometry" />
    </mxCell>

    <mxCell id="e_s1_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#7f8c8d;strokeWidth=1.5;" edge="1" source="b_s1_tbl" target="b_s1_doc" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_s1_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#7f8c8d;strokeWidth=1.5;" edge="1" source="b_s1_doc" target="b_s1_out" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <!-- ======================================================== -->
    <!-- STAGE 2: SCHEMA-PRESERVING MULTIGRAPH (Sec. 3.2) -->
    <!-- ======================================================== -->
    <mxCell id="p_s2" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fbfcfc;strokeColor=#8e44ad;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="360" y="100" width="310" height="510" as="geometry" />
    </mxCell>
    <mxCell id="t_s2" value="&lt;b&gt;Stage 2 (Sec. 3.2): Multigraph Construction&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e8daef;strokeColor=#8e44ad;fontSize=11;fontColor=#512e5f;" vertex="1" parent="1">
      <mxGeometry x="375" y="115" width="280" height="32" as="geometry" />
    </mxCell>

    <!-- Multigraph Miniature Nodes -->
    <mxCell id="g_ent_club" value="Toronto&lt;br&gt;Eagles" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ebf5fb;strokeColor=#3498db;fontSize=9;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="385" y="160" width="70" height="32" as="geometry" />
    </mxCell>
    <mxCell id="g_rec_node" value="ρ0&lt;br&gt;(Rec 0)" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e8daef;strokeColor=#8e44ad;fontSize=9;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="385" y="215" width="70" height="32" as="geometry" />
    </mxCell>
    <mxCell id="g_lit_year" value="&amp;quot;1989&amp;quot;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#eaeded;strokeColor=#7f8c8d;fontSize=9;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="385" y="270" width="70" height="28" as="geometry" />
    </mxCell>
    <mxCell id="g_ent_city" value="Toronto" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e8f8f5;strokeColor=#1abc9c;fontSize=9;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="545" y="215" width="75" height="32" as="geometry" />
    </mxCell>
    <mxCell id="g_doc_node" value="Doc:&lt;br&gt;Toronto" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fef5e7;strokeColor=#e67e22;fontSize=9;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="545" y="270" width="75" height="32" as="geometry" />
    </mxCell>
    <mxCell id="g_ans_node" value="York" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fadbd8;strokeColor=#e74c3c;fontSize=9;fontStyle=1;" vertex="1" parent="1">
      <mxGeometry x="545" y="325" width="75" height="28" as="geometry" />
    </mxCell>

    <!-- Graph Edges -->
    <mxCell id="ge_1" value="rec" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#8e44ad;fontSize=9;" edge="1" source="g_ent_club" target="g_rec_node" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="ge_2" value="city" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#1abc9c;fontSize=9;" edge="1" source="g_rec_node" target="g_ent_city" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="ge_3" value="formed" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#7f8c8d;fontSize=9;" edge="1" source="g_rec_node" target="g_lit_year" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="ge_4" value="link" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#e67e22;fontSize=9;" edge="1" source="g_ent_city" target="g_doc_node" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="ge_5" value="orig_name" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#e74c3c;fontSize=9;" edge="1" source="g_doc_node" target="g_ans_node" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <mxCell id="b_s2_cent" value="&lt;b&gt;Star Centroid Hub G*(ρi) (&amp;lt; 20 ms)&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Centroid binds row cells (Prop. 1)&lt;br&gt;• Mathematically precludes row conflation&lt;br&gt;• Deterministic rule text extraction (0 LLM)&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f4ecf7;strokeColor=#af7ac5;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="375" y="375" width="280" height="75" as="geometry" />
    </mxCell>
    <mxCell id="b_s2_path" value="&lt;b&gt;Guided Path Scorer S(p) (9 Factors)&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Path p1: Eagles → ρ0 → Toronto → York&lt;br&gt;• Maximal score S(p1) = 7.85 (non-filtering)&lt;br&gt;• Lossless compression X*(G_q) scaffold&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f4ecf7;strokeColor=#8e44ad;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="375" y="465" width="280" height="80" as="geometry" />
    </mxCell>

    <!-- ======================================================== -->
    <!-- STAGE 3: TWO-TIER CONTROLLED REASONING ENGINE (Sec. 3.3) -->
    <!-- ======================================================== -->
    <mxCell id="p_s3" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fef9e7;strokeColor=#e67e22;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="710" y="100" width="350" height="510" as="geometry" />
    </mxCell>
    <mxCell id="t_s3" value="&lt;b&gt;Stage 3 (Sec. 3.3): Two-Tier Controlled Engine&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fdebd0;strokeColor=#e67e22;fontSize=11;fontColor=#7e5109;" vertex="1" parent="1">
      <mxGeometry x="725" y="115" width="320" height="32" as="geometry" />
    </mxCell>
    <mxCell id="b_s3_l1" value="&lt;b&gt;Tier 1: L1 Reader (First LLM Call)&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Evaluates compressed multigraph X*(G_q) + path p1&lt;br&gt;• &lt;b&gt;Controlled Audit Decision&lt;/b&gt;:&lt;br&gt;&amp;nbsp;&amp;nbsp;- If determined (|C_q|=1) → &lt;b style='color:#1e8449;'&gt;Fast Exit Answer&lt;/b&gt; (1 turn)&lt;br&gt;&amp;nbsp;&amp;nbsp;- If collision (|C_q|&amp;gt;1) or missing link → &lt;b style='color:#d35400;'&gt;Diagnostic Handoff&lt;/b&gt;&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#f39c12;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="725" y="160" width="320" height="85" as="geometry" />
    </mxCell>
    <mxCell id="b_s3_diag" value="&lt;b&gt;Diagnostic Handoff H_diag&lt;/b&gt;: &lt;code style='background:#fcf3cf;'&gt;{&amp;quot;focus&amp;quot;: [ρ0, ρ1], &amp;quot;check&amp;quot;: &amp;quot;town&amp;quot;}&lt;/code&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fef5e7;strokeColor=#d35400;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="725" y="270" width="320" height="40" as="geometry" />
    </mxCell>
    <mxCell id="b_s3_bridge" value="&lt;b&gt;Targeted Symmetric Bridge Augmentation ΔD&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;Harvests missing candidate passages symmetrically for focus set C_focus&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f4ecf7;strokeColor=#8e44ad;fontSize=10;" vertex="1" parent="1">
      <mxGeometry x="725" y="335" width="320" height="50" as="geometry" />
    </mxCell>
    <mxCell id="b_s3_l2" value="&lt;b&gt;Tier 2: L2 Reader (Second LLM Call)&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Input: &lt;b&gt;Minimal Sufficient State Capsule K_L2&lt;/b&gt; (Prop. 2)&lt;br&gt;• Conclusive factual resolution (eliminates tiebreak guessing)&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e8f8f5;strokeColor=#16a085;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="725" y="415" width="320" height="70" as="geometry" />
    </mxCell>

    <mxCell id="e_s3_1" value="if collision" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#d35400;strokeWidth=1.5;fontColor=#b9770e;fontSize=9;" edge="1" source="b_s3_l1" target="b_s3_diag" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_s3_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#8e44ad;strokeWidth=1.5;" edge="1" source="b_s3_diag" target="b_s3_bridge" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_s3_3" value="State Capsule K_L2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#16a085;strokeWidth=1.5;fontColor=#117864;fontSize=9;" edge="1" source="b_s3_bridge" target="b_s3_l2" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <!-- ======================================================== -->
    <!-- STAGE 4: GROUNDED GENERATION & PROVENANCE AUDIT (Sec. 3.4) -->
    <!-- ======================================================== -->
    <mxCell id="p_s4" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f9fcfb;strokeColor=#16a085;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="1100" y="100" width="290" height="510" as="geometry" />
    </mxCell>
    <mxCell id="t_s4" value="&lt;b&gt;Stage 4 (Sec. 3.4): Grounded Provenance&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d1f2eb;strokeColor=#16a085;fontSize=11;fontColor=#0e6251;" vertex="1" parent="1">
      <mxGeometry x="1115" y="115" width="260" height="32" as="geometry" />
    </mxCell>
    <mxCell id="b_s4_ans" value="&lt;b&gt;Verified Output Span a*&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:center; margin:4px 0;'&gt;&lt;span style='background:#d4efdf; color:#145a32; font-weight:bold; font-size:13px; padding:3px 12px; border-radius:3px;'&gt;&amp;quot;York&amp;quot;&lt;/span&gt;&lt;/div&gt;&lt;div style='font-size:10px;'&gt;• Exact context-grounded extraction&lt;br&gt;• Zero ungrounded hallucination&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#27ae60;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="1115" y="160" width="260" height="85" as="geometry" />
    </mxCell>
    <mxCell id="b_s4_prov" value="&lt;b&gt;Auditable Provenance π(a*)&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px; line-height:1.3;'&gt;• Table: &lt;code&gt;AFL_Ontario_0&lt;/code&gt;&lt;br&gt;• Row Hub: ρ0 (&lt;code&gt;row:0&lt;/code&gt;)&lt;br&gt;• Cell: &lt;code&gt;City: Toronto&lt;/code&gt;&lt;br&gt;• Bridge URL: &lt;code&gt;/wiki/Toronto&lt;/code&gt;&lt;br&gt;• Passage: &lt;i&gt;&amp;quot;...town of York...&amp;quot;&lt;/i&gt;&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#16a085;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="1115" y="270" width="260" height="115" as="geometry" />
    </mxCell>
    <mxCell id="b_s4_rev" value="&lt;b&gt;Reverse Grounding Fallback&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Maps span back onto multigraph G_q&lt;br&gt;• Direct evidence synthesis if disconnected&lt;br&gt;• 0.53% empty rate (92.0% faithful traces)&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ebf5fb;strokeColor=#2980b9;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="1115" y="410" width="260" height="85" as="geometry" />
    </mxCell>

    <mxCell id="e_s4_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#27ae60;strokeWidth=1.5;" edge="1" source="b_s4_ans" target="b_s4_prov" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_s4_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#16a085;strokeWidth=1.5;" edge="1" source="b_s4_prov" target="b_s4_rev" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <!-- ======================================================== -->
    <!-- INTER-STAGE CONNECTORS (Orthogonal & Neat) -->
    <!-- ======================================================== -->
    <!-- Query -> Stage 1 -->
    <mxCell id="e_q_s1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#2980b9;strokeWidth=2;" edge="1" source="b_q" target="t_s1" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>

    <!-- Stage 1 -> Stage 2 -->
    <mxCell id="e_s1_s2" value="Evidence" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#2980b9;strokeWidth=2;fontColor=#1b4f72;fontSize=10;fontStyle=1;" edge="1" source="b_s1_out" target="b_s2_cent" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>

    <!-- Stage 2 -> Stage 3 -->
    <mxCell id="e_s2_s3" value="X*(G_q), p1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#8e44ad;strokeWidth=2;fontColor=#512e5f;fontSize=10;fontStyle=1;" edge="1" source="b_s2_path" target="b_s3_l1" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>

    <!-- Stage 3 -> Stage 4 (Branch 1: Fast Exit) -->
    <mxCell id="e_s3_out_fast" value="Fast Exit (1 turn)" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#27ae60;strokeWidth=2;fontColor=#1e8449;fontSize=10;fontStyle=1;" edge="1" source="b_s3_l1" target="b_s4_ans" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>

    <!-- Stage 3 -> Stage 4 (Branch 2: Tier 2 Exit) -->
    <mxCell id="e_s3_out_l2" value="L2 Verified Exit" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#16a085;strokeWidth=2;fontColor=#0e6251;fontSize=10;fontStyle=1;" edge="1" source="b_s3_l2" target="b_s4_ans" parent="1">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="1080" y="450" />
          <mxPoint x="1080" y="215" />
        </Array>
      </mxGeometry>
    </mxCell>

  </root>
</mxGraphModel>"""

with open('/workspace/kiennt/online-kg-rag/paper_v2/figures/fig2_system_pipeline.drawio', 'w', encoding='utf-8') as f:
    f.write(fig2_xml)

print('Saved fig2_system_pipeline.drawio successfully!')
