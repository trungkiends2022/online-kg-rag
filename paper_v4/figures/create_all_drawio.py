# Create drawio files for Figure 1 and Figure 2 as well

# Figure 1: Paradigm Comparison
fig1_xml = """<mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1300" pageHeight="450" background="#ffffff">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />

    <!-- Paradigm A: Direct LLM Prompting -->
    <mxCell id="p_a" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8f9fa;strokeColor=#bdc3c7;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="30" y="30" width="370" height="380" as="geometry" />
    </mxCell>
    <mxCell id="t_a" value="&lt;b&gt;(A) Direct LLM Prompting&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#eaeded;strokeColor=#bdc3c7;fontSize=13;fontColor=#2c3e50;" vertex="1" parent="1">
      <mxGeometry x="45" y="45" width="340" height="35" as="geometry" />
    </mxCell>
    <mxCell id="b_a_in" value="&lt;b&gt;Serialized Context Pool&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10.5px;'&gt;• Table rows flattened into text strings&lt;br&gt;• External text passages concatenated&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#bdc3c7;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="95" width="340" height="70" as="geometry" />
    </mxCell>
    <mxCell id="b_a_model" value="&lt;b&gt;Frozen Backbone LLM&lt;/b&gt;&lt;br&gt;&lt;div style='font-size:10.5px;'&gt;Single unguided forward pass&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#eaf2f8;strokeColor=#aed6f1;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="190" width="340" height="55" as="geometry" />
    </mxCell>
    <mxCell id="b_a_lim" value="&lt;b style='color:#c0392b;'&gt;Key Limitations&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10.5px; color:#922b21;'&gt;• Loss of tabular row-column bindings&lt;br&gt;• Hallucinates under candidate collisions&lt;br&gt;• Unguided attention across long context&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fdedec;strokeColor=#f5b7b1;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="45" y="270" width="340" height="90" as="geometry" />
    </mxCell>
    <mxCell id="e_a_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#7f8c8d;strokeWidth=1.5;" edge="1" source="b_a_in" target="b_a_model" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_a_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#7f8c8d;strokeWidth=1.5;" edge="1" source="b_a_model" target="b_a_lim" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <!-- Paradigm B: Destructive Graph Pruning (ODYSSEY) -->
    <mxCell id="p_b" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fdf7f7;strokeColor=#e6b8af;strokeWidth=1.5;" vertex="1" parent="1">
      <mxGeometry x="450" y="30" width="370" height="380" as="geometry" />
    </mxCell>
    <mxCell id="t_b" value="&lt;b&gt;(B) Destructive Graph Pruning&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f4cccc;strokeColor=#e06666;fontSize=13;fontColor=#990000;" vertex="1" parent="1">
      <mxGeometry x="465" y="45" width="340" height="35" as="geometry" />
    </mxCell>
    <mxCell id="b_b_in" value="&lt;b&gt;Question-Guided Graph Pruning&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10.5px;'&gt;• Constructs hybrid graph over entities&lt;br&gt;• Discards ~53% nodes/edges via heuristics&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#e06666;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="465" y="95" width="340" height="70" as="geometry" />
    </mxCell>
    <mxCell id="b_b_model" value="&lt;b&gt;Pruned Subgraph Prompting&lt;/b&gt;&lt;br&gt;&lt;div style='font-size:10.5px;'&gt;Linearized surviving triples&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fce5cd;strokeColor=#f6b26b;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="465" y="190" width="340" height="55" as="geometry" />
    </mxCell>
    <mxCell id="b_b_lim" value="&lt;b style='color:#c0392b;'&gt;Key Limitations&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10.5px; color:#922b21;'&gt;• Peripheral evidence loss (drops key facts)&lt;br&gt;• Arbitrary tie-breaking when candidates tie&lt;br&gt;• Exact match collapses on multi-hop spans&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fdedec;strokeColor=#f5b7b1;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="465" y="270" width="340" height="90" as="geometry" />
    </mxCell>
    <mxCell id="e_b_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#e06666;strokeWidth=1.5;" edge="1" source="b_b_in" target="b_b_model" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_b_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#e06666;strokeWidth=1.5;" edge="1" source="b_b_model" target="b_b_lim" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

    <!-- Paradigm C: OUEG-RAG (Ours) -->
    <mxCell id="p_c" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f0fdf9;strokeColor=#27ae60;strokeWidth=2;" vertex="1" parent="1">
      <mxGeometry x="870" y="30" width="390" height="380" as="geometry" />
    </mxCell>
    <mxCell id="t_c" value="&lt;b&gt;(C) OUEG-RAG (Controlled Scaffolding)&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5f5e3;strokeColor=#27ae60;fontSize=13;fontColor=#1e8449;" vertex="1" parent="1">
      <mxGeometry x="885" y="45" width="360" height="35" as="geometry" />
    </mxCell>
    <mxCell id="b_c_in" value="&lt;b&gt;Complete Evidence Graph + Guided Path&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10.5px;'&gt;• 100% evidence preserved via prompt compression&lt;br&gt;• Deterministic path p₁ (S(p)) as non-filtering guide&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#27ae60;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="885" y="95" width="360" height="70" as="geometry" />
    </mxCell>
    <mxCell id="b_c_model" value="&lt;b&gt;Bounded Two-Tier Controlled Execution&lt;/b&gt;&lt;br&gt;&lt;div style='font-size:10.5px;'&gt;L1 Fast Exit OR L2 Targeted Diagnostic Augmentation&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5f5e3;strokeColor=#27ae60;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="885" y="190" width="360" height="55" as="geometry" />
    </mxCell>
    <mxCell id="b_c_lim" value="&lt;b style='color:#1e8449;'&gt;Key Advantages&lt;/b&gt;&lt;br&gt;&lt;div style='text-align:left; font-size:10.5px; color:#145a32;'&gt;• Zero peripheral evidence loss&lt;br&gt;• Resolves collisions factually via bridge retrieval&lt;br&gt;• High provenance faithfulness (92.0%)&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e8f8f5;strokeColor=#a3e4d7;fontSize=11;" vertex="1" parent="1">
      <mxGeometry x="885" y="270" width="360" height="90" as="geometry" />
    </mxCell>
    <mxCell id="e_c_1" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#27ae60;strokeWidth=1.5;" edge="1" source="b_c_in" target="b_c_model" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>
    <mxCell id="e_c_2" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#27ae60;strokeWidth=1.5;" edge="1" source="b_c_model" target="b_c_lim" parent="1"><mxGeometry relative="1" as="geometry" /></mxCell>

  </root>
</mxGraphModel>"""

with open('/workspace/kiennt/online-kg-rag/paper_v2/figures/fig1_paradigm_comparison.drawio', 'w', encoding='utf-8') as f:
    f.write(fig1_xml)

print("Saved fig1_paradigm_comparison.drawio successfully!")
