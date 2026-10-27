fig2_xml = """<mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1400" pageHeight="550" background="#ffffff">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />

    <!-- Stage 1: Retrieval -->
    <mxCell id="p_s1" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8f9fa;strokeColor=#bdc3c7;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="30" y="30" width="280" height="460" as="geometry" />
    </mxCell>
    <mxCell id="t_s1" value="&lt;b&gt;Stage 1: Evidence Ingestion&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#eaeded;strokeColor=#bdc3c7;fontSize=12;fontColor=#2c3e50;" vertex="1" parent="1">
      <mxGeometry x="45" y="45" width="250" height="35" as="geometry" />
    </mxCell>
    <mxCell id="b_s1_q" value="&lt;b&gt;Input Query q&lt;/b&gt;&lt;br&gt;&lt;i style='font-size:10px;'&gt;&quot;City with AFL club in 1989?&quot;&lt;/i&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#bdc3c7;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="95" width="250" height="50" as="geometry" />
    </mxCell>
    <mxCell id="b_s1_tbl" value="&lt;b&gt;Coarse Row Retrieval&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Lexical &amp;amp; anchor constraint index&lt;br&gt;• Top-k1 rows (k1=5)&lt;br&gt;• Identifies candidate row ρ0&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#bdc3c7;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="165" width="250" height="75" as="geometry" />
    </mxCell>
    <mxCell id="b_s1_doc" value="&lt;b&gt;Hyperlink Passage Expansion&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Harvests candidate cell links&lt;br&gt;• Budget: k2=3 passages&lt;br&gt;• Traverses Toronto → Doc:Toronto&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#bdc3c7;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="260" width="250" height="75" as="geometry" />
    </mxCell>
    <mxCell id="e_s1_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#7f8c8d;strokeWidth=1.5;" edge="1" source="b_s1_q" target="b_s1_tbl" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_s1_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#7f8c8d;strokeWidth=1.5;" edge="1" source="b_s1_tbl" target="b_s1_doc" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <!-- Stage 2: Multigraph Construction -->
    <mxCell id="p_s2" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#effaf6;strokeColor=#a2d9ce;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="340" y="30" width="320" height="460" as="geometry" />
    </mxCell>
    <mxCell id="t_s2" value="&lt;b&gt;Stage 2: Schema-Preserving Graph&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d1f2eb;strokeColor=#a2d9ce;fontSize=12;fontColor=#117864;" vertex="1" parent="1">
      <mxGeometry x="355" y="45" width="290" height="35" as="geometry" />
    </mxCell>
    <mxCell id="b_s2_cent" value="&lt;b&gt;Record Centroid Bindings&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Star subgraph G*(ρi) per row&lt;br&gt;• Precludes horizontal conflation&lt;br&gt;• &amp;lt; 20 ms deterministic build (0 LLM)&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a2d9ce;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="355" y="95" width="290" height="75" as="geometry" />
    </mxCell>
    <mxCell id="b_s2_link" value="&lt;b&gt;Hyperlink &amp;amp; Text Triples&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Hyperlink edges: Cell → Doc:Page&lt;br&gt;• Deterministic rule-based text extraction&lt;br&gt;• Forms connected multigraph G_q&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a2d9ce;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="355" y="190" width="290" height="75" as="geometry" />
    </mxCell>
    <mxCell id="b_s2_path" value="&lt;b&gt;Deterministic Path Ranking S(p)&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Evaluates 9-dimensional alignment vector&lt;br&gt;• Ranks path p₁ (Score S=7.85)&lt;br&gt;• Serves as non-filtering attention guide&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#a2d9ce;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="355" y="285" width="290" height="85" as="geometry" />
    </mxCell>
    <mxCell id="e_s2_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#16a085;strokeWidth=1.5;" edge="1" source="b_s2_cent" target="b_s2_link" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_s2_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#16a085;strokeWidth=1.5;" edge="1" source="b_s2_link" target="b_s2_path" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <!-- Stage 3: Two-Tier Controlled Reasoning Engine -->
    <mxCell id="p_s3" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fef9e7;strokeColor=#f9e79f;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="690" y="30" width="370" height="460" as="geometry" />
    </mxCell>
    <mxCell id="t_s3" value="&lt;b&gt;Stage 3: Two-Tier Controlled Engine&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fcf3cf;strokeColor=#f9e79f;fontSize=12;fontColor=#7d6608;" vertex="1" parent="1">
      <mxGeometry x="705" y="45" width="340" height="35" as="geometry" />
    </mxCell>
    <mxCell id="b_s3_l1" value="&lt;b&gt;Tier 1: L1 Reader &amp;amp; Self-Audit&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Evaluates compressed multigraph + guide path p₁&lt;br&gt;• &lt;b&gt;Fast Exit&lt;/b&gt;: Returns verified answer if unambiguous&lt;br&gt;• &lt;b&gt;Diagnostic Handoff&lt;/b&gt;: Defers if candidates collide&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#f39c12;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="705" y="95" width="340" height="85" as="geometry" />
    </mxCell>
    <mxCell id="b_s3_bridge" value="&lt;b&gt;Diagnostic Bridge Expansion&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Symmetric retrieval of missing passages for {ρ0, ρ1}&lt;br&gt;• Packages state capsule K_L2&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#9b59b6;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="705" y="210" width="340" height="65" as="geometry" />
    </mxCell>
    <mxCell id="b_s3_l2" value="&lt;b&gt;Tier 2: L2 Resolution&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10px;'&gt;• Factual evaluation over state capsule K_L2&lt;br&gt;• Conclusive grounded answer without guessing&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#27ae60;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="705" y="305" width="340" height="65" as="geometry" />
    </mxCell>
    <mxCell id="e_s3_1" value="if collision" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#f39c12;strokeWidth=1.5;fontColor=#b9770e;fontSize=10;" edge="1" source="b_s3_l1" target="b_s3_bridge" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_s3_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#27ae60;strokeWidth=1.5;" edge="1" source="b_s3_bridge" target="b_s3_l2" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <!-- Final Output -->
    <mxCell id="b_out" value="&lt;b&gt;Grounded Verified Output&lt;/b&gt;&lt;br&gt;&lt;span style='background:#d5e8d4; color:#274e13; font-weight:bold; font-size:12px; padding:3px 8px; border-radius:3px;'&gt;&quot;York&quot;&lt;/span&gt;&lt;br&gt;&lt;div style='font-size:10px; margin-top:4px;'&gt;Provenanced to: Row 0 → Doc:Toronto → text span&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="1090" y="200" width="280" height="90" as="geometry" />
    </mxCell>

    <!-- Connectors between stages -->
    <mxCell id="e_cross_s1_s2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#2c3e50;strokeWidth=2;" edge="1" source="b_s1_doc" target="b_s2_cent" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_cross_s2_s3" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#16a085;strokeWidth=2;" edge="1" source="b_s2_path" target="b_s3_l1" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_cross_s3_out1" value="Fast Exit" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#82b366;strokeWidth=2;dashed=1;fontColor=#274e13;fontSize=10;" edge="1" source="b_s3_l1" target="b_out" parent="1">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="1070" y="137" />
          <mxPoint x="1070" y="230" />
        </Array>
      </mxGeometry>
    </mxCell>
    <mxCell id="e_cross_s3_out2" value="Tier 2 Exit" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#27ae60;strokeWidth=2;fontColor=#1e8449;fontSize=10;" edge="1" source="b_s3_l2" target="b_out" parent="1">
      <mxGeometry relative="1" as="geometry">
        <Array as="points">
          <mxPoint x="1070" y="337" />
          <mxPoint x="1070" y="260" />
        </Array>
      </mxGeometry>
    </mxCell>

  </root>
</mxGraphModel>"""

with open('/workspace/kiennt/online-kg-rag/paper_v2/figures/fig2_system_pipeline.drawio', 'w', encoding='utf-8') as f:
    f.write(fig2_xml)

print("Saved fig2_system_pipeline.drawio successfully!")
