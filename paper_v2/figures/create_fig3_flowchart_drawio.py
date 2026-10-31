import xml.etree.ElementTree as ET

def generate_fig3_drawio():
    xml = """<mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1350" pageHeight="700" background="#ffffff">
  <root>
    <mxCell id="0" />
    <mxCell id="1" parent="0" />

    <!-- ==================== COLUMN 1: TIER 1 ==================== -->
    <!-- Background Panel 1 -->
    <mxCell id="p1" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f8fbfd;strokeColor=#2980b9;strokeWidth=2;arcSize=4;" vertex="1" parent="1">
      <mxGeometry x="40" y="30" width="480" height="620" as="geometry" />
    </mxCell>
    <!-- Header Tier 1 -->
    <mxCell id="t1" value="&lt;b&gt;Tier 1: Initial Evidence Reasoning Algorithm&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d4e6f1;strokeColor=#2980b9;strokeWidth=1.5;fontSize=14;fontColor=#1b4f72;" vertex="1" parent="1">
      <mxGeometry x="60" y="45" width="440" height="42" as="geometry" />
    </mxCell>

    <!-- Step 1: Input Multigraph -->
    <mxCell id="b1_in" value="&lt;b style='font-size:13px; color:#1b4f72;'&gt;Input: Full Evidence Multigraph G&lt;sub&gt;q&lt;/sub&gt;&lt;/b&gt;&lt;br&gt;&lt;span style='font-size:11px; color:#566573;'&gt;Full unpruned multigraph (all candidate rows &amp;amp; connected passages)&lt;br&gt;Tied candidates: &lt;i&gt;Toronto Eagles (1989)&lt;/i&gt; vs &lt;i&gt;Toronto Blues (1989)&lt;/i&gt;&lt;/span&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#3498db;strokeWidth=1.5;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="60" y="110" width="440" height="75" as="geometry" />
    </mxCell>

    <!-- Step 2: Primary LLM Reasoning (Brain Icon) -->
    <mxCell id="b1_llm" value="&lt;b style='font-size:13px; color:#512e5f;'&gt;[LLM] Step 1: Primary LLM Reasoning (Call 1)&lt;/b&gt;&lt;br&gt;&lt;span style='font-size:11px; color:#4a235a;'&gt;Evaluates evidence against query constraints; strict clarity audit&lt;br&gt;&lt;b&gt;Audit Rule:&lt;/b&gt; Zero ungrounded guessing on candidate ties&lt;/span&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f4ecf7;strokeColor=#8e44ad;strokeWidth=2;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="60" y="215" width="440" height="75" as="geometry" />
    </mxCell>

    <!-- Step 3: Decision Rhombus -->
    <mxCell id="b1_dec" value="&lt;b style='font-size:12px;'&gt;Candidate&lt;br&gt;Collision?&lt;/b&gt;" style="rhombus;whiteSpace=wrap;html=1;fillColor=#fbfcfc;strokeColor=#8e44ad;strokeWidth=2;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="195" y="325" width="170" height="90" as="geometry" />
    </mxCell>

    <!-- Branch A: Fast Exit -->
    <mxCell id="b1_exit" value="&lt;b style='color:#145a32; font-size:13px;'&gt;Fast Exit&lt;/b&gt;&lt;br&gt;&lt;span style='font-size:11px; color:#196f3d;'&gt;Single LLM Call&lt;br&gt;&lt;b&gt;≈ 80% of Queries&lt;/b&gt;&lt;/span&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d4efdf;strokeColor=#27ae60;strokeWidth=2;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="60" y="475" width="200" height="120" as="geometry" />
    </mxCell>

    <!-- Branch B: Diagnostic Handoff -->
    <mxCell id="b1_out" value="&lt;b style='color:#7e5109; font-size:13px;'&gt;Diagnostic Packet D&lt;/b&gt;&lt;br&gt;&lt;span style='font-size:11px; color:#935116;'&gt;Collision Alert:&lt;br&gt;Both clubs match 1989;&lt;br&gt;Bridge passage missing&lt;br&gt;&lt;b&gt;Controlled Pause (No guess)&lt;/b&gt;&lt;/span&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#fdebd0;strokeColor=#d35400;strokeWidth=2;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="300" y="475" width="200" height="120" as="geometry" />
    </mxCell>

    <!-- Connectors inside Tier 1 -->
    <mxCell id="e1_1" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#2980b9;strokeWidth=2;endArrow=block;endFill=1;" edge="1" source="b1_in" target="b1_llm" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e1_2" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#8e44ad;strokeWidth=2;endArrow=block;endFill=1;" edge="1" source="b1_llm" target="b1_dec" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e1_no" value="&lt;b style='color:#27ae60; background:#ffffff; padding:2px;'&gt;No (Clear)&lt;/b&gt;" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#27ae60;strokeWidth=2;endArrow=block;endFill=1;exitX=0;exitY=0.5;entryX=0.5;entryY=0;" edge="1" source="b1_dec" target="b1_exit" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e1_yes" value="&lt;b style='color:#d35400; background:#ffffff; padding:2px;'&gt;Yes (Tied)&lt;/b&gt;" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#d35400;strokeWidth=2;endArrow=block;endFill=1;exitX=1;exitY=0.5;entryX=0.5;entryY=0;" edge="1" source="b1_dec" target="b1_out" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>


    <!-- ==================== CENTER: BRIDGE &amp; GRAPH COMPRESSION ==================== -->
    <mxCell id="b_bridge" value="&lt;b style='font-size:13px; color:#0e6251;'&gt;Automated Bridge Search&lt;br&gt;&amp;amp; Graph Compression&lt;/b&gt;&lt;hr style='border-top:1px solid #16a085; margin:6px 0;'&gt;&lt;div style='text-align:center; font-size:11.5px; line-height:1.4;'&gt;&lt;b style='color:#2980b9;'&gt;Zero LLM Calls&lt;/b&gt;&lt;br&gt;&lt;br&gt;&lt;b style='color:#0e6251;'&gt;Graph Compression:&lt;/b&gt;&lt;br&gt;Prune non-tied paths&lt;br&gt;&lt;b style='color:#c0392b;'&gt;≈ 85% Size Reduction&lt;/b&gt;&lt;br&gt;&lt;br&gt;Fetch missing bridge passage:&lt;br&gt;&lt;i&gt;Doc:Toronto_Blues&lt;/i&gt;&lt;/div&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e8f8f5;strokeColor=#16a085;strokeWidth=2;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="560" y="240" width="220" height="210" as="geometry" />
    </mxCell>

    <!-- Connectors through Bridge -->
    <mxCell id="e_bridge_in" value="&lt;b style='color:#d35400; background:#ffffff; padding:2px;'&gt;Handoff D&lt;/b&gt;" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#d35400;strokeWidth=2.5;endArrow=block;endFill=1;exitX=1;exitY=0.5;entryX=0.5;entryY=1;" edge="1" source="b1_out" target="b_bridge" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e_bridge_out" value="&lt;b style='color:#16a085; background:#ffffff; padding:2px;'&gt;Minimal Capsule S_min&lt;/b&gt;" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#16a085;strokeWidth=2.5;endArrow=block;endFill=1;exitX=0.5;exitY=0;entryX=0;entryY=0.5;" edge="1" source="b_bridge" target="b2_in" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>


    <!-- ==================== COLUMN 2: TIER 2 ==================== -->
    <!-- Background Panel 2 -->
    <mxCell id="p2" value="" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f6fcfa;strokeColor=#16a085;strokeWidth=2;arcSize=4;" vertex="1" parent="1">
      <mxGeometry x="820" y="30" width="480" height="620" as="geometry" />
    </mxCell>
    <!-- Header Tier 2 -->
    <mxCell id="t2" value="&lt;b&gt;Tier 2: Targeted Collision Resolution Algorithm&lt;/b&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d1f2eb;strokeColor=#16a085;strokeWidth=1.5;fontSize=14;fontColor=#0e6251;" vertex="1" parent="1">
      <mxGeometry x="840" y="45" width="440" height="42" as="geometry" />
    </mxCell>

    <!-- Step 1: Input Minimal Capsule -->
    <mxCell id="b2_in" value="&lt;b style='font-size:13px; color:#0e6251;'&gt;Input: Minimal State Capsule S&lt;sub&gt;min&lt;/sub&gt;&lt;/b&gt;&lt;br&gt;&lt;span style='font-size:11px; color:#566573;'&gt;Compressed isolated subgraph: contains strictly tied clubs + bridge passage&lt;br&gt;Zero non-competing candidates; eliminates context dilution&lt;/span&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#16a085;strokeWidth=1.5;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="840" y="110" width="440" height="75" as="geometry" />
    </mxCell>

    <!-- Step 2: Targeted LLM Call (Brain Icon) -->
    <mxCell id="b2_llm" value="&lt;b style='font-size:13px; color:#512e5f;'&gt;[LLM] Step 2: Targeted LLM Resolution (Call 2)&lt;/b&gt;&lt;br&gt;&lt;span style='font-size:11px; color:#4a235a;'&gt;Prompts LLM exclusively with compressed capsule S&lt;sub&gt;min&lt;/sub&gt;&lt;br&gt;Resolves ambiguity directly against factual bridge evidence&lt;/span&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#f4ecf7;strokeColor=#8e44ad;strokeWidth=2;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="840" y="215" width="440" height="75" as="geometry" />
    </mxCell>

    <!-- Step 3: Decision Rhombus -->
    <mxCell id="b2_dec" value="&lt;b style='font-size:12px;'&gt;Grounded by&lt;br&gt;Bridge Passage?&lt;/b&gt;" style="rhombus;whiteSpace=wrap;html=1;fillColor=#fbfcfc;strokeColor=#16a085;strokeWidth=2;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="975" y="325" width="170" height="90" as="geometry" />
    </mxCell>

    <!-- Step 4: Final Verified Output -->
    <mxCell id="b2_out" value="&lt;b style='color:#145a32; font-size:14px;'&gt;Verified Output: Answer &quot;York&quot;&lt;/b&gt;&lt;br&gt;&lt;span style='font-size:11.5px; color:#196f3d;'&gt;≤ 2 LLM Calls Total &amp;nbsp;•&amp;nbsp; 100% Grounded Provenance &amp;nbsp;•&amp;nbsp; Zero Hallucination&lt;br&gt;&lt;b&gt;Provenance Trace:&lt;/b&gt; Row 0 → &lt;i&gt;Doc:Toronto_Blues&lt;/i&gt; → &lt;b&gt;York University&lt;/b&gt;&lt;/span&gt;" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d4efdf;strokeColor=#27ae60;strokeWidth=2;fontSize=12;" vertex="1" parent="1">
      <mxGeometry x="840" y="475" width="440" height="120" as="geometry" />
    </mxCell>

    <!-- Connectors inside Tier 2 -->
    <mxCell id="e2_1" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#16a085;strokeWidth=2;endArrow=block;endFill=1;" edge="1" source="b2_in" target="b2_llm" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e2_2" value="" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#8e44ad;strokeWidth=2;endArrow=block;endFill=1;" edge="1" source="b2_llm" target="b2_dec" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>
    <mxCell id="e2_yes" value="&lt;b style='color:#27ae60; background:#ffffff; padding:2px;'&gt;Yes (Grounded)&lt;/b&gt;" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;strokeColor=#27ae60;strokeWidth=2.5;endArrow=block;endFill=1;exitX=0.5;exitY=1;entryX=0.5;entryY=0;" edge="1" source="b2_dec" target="b2_out" parent="1">
      <mxGeometry relative="1" as="geometry" />
    </mxCell>

  </root>
</mxGraphModel>"""
    return xml

if __name__ == "__main__":
    content = generate_fig3_drawio()
    with open('/workspace/kiennt/online-kg-rag/paper_v2/figures/fig3_two_tier_reasoning.drawio', 'w') as f:
        f.write(content)
    with open('/workspace/kiennt/online-kg-rag/paper_v2/figures/fig3_diagnostic_l2.drawio', 'w') as f:
        f.write(content)
    print("Exported XML successfully!")
