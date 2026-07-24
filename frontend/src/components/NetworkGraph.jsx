import React, { useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function NetworkGraph() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });

  useEffect(() => {
    // Generate sample 2D graph data for visual demo
    const nodes = [];
    const links = [];

    for (let i = 0; i < 25; i++) {
      const isMule = i < 5;
      nodes.push({
        id: `ACC-${i.toString().padStart(5, '0')}`,
        name: `Account ${i}`,
        val: isMule ? 12 : 6,
        color: isMule ? '#ef4444' : '#00f2fe'
      });
    }

    // Connect mule ring cluster
    links.push({ source: 'ACC-00000', target: 'ACC-00001' });
    links.push({ source: 'ACC-00001', target: 'ACC-00002' });
    links.push({ source: 'ACC-00002', target: 'ACC-00003' });
    links.push({ source: 'ACC-00003', target: 'ACC-00004' });
    links.push({ source: 'ACC-00004', target: 'ACC-00000' });

    // Connect normal nodes
    for (let i = 5; i < 24; i++) {
      links.push({ source: `ACC-${i.toString().padStart(5, '0')}`, target: `ACC-${(i + 1).toString().padStart(5, '0')}` });
    }

    setGraphData({ nodes, links });
  }, []);

  return (
    <div className="glass-card" style={{ margin: '24px', height: '600px', position: 'relative' }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '12px' }}>
        Unified Entity Graph Topology (NetworkX)
      </h2>
      <div style={{ width: '100%', height: '520px', borderRadius: '8px', overflow: 'hidden', background: '#070a0f' }}>
        <ForceGraph2D
          graphData={graphData}
          nodeAutoColorBy="color"
          nodeCanvasObject={(node, ctx, globalScale) => {
            const label = node.id;
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px Inter`;
            ctx.fillStyle = node.color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false);
            ctx.fill();

            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#ffffff';
            ctx.fillText(label, node.x, node.y + node.val + 8);
          }}
          linkColor={() => 'rgba(255, 255, 255, 0.15)'}
        />
      </div>
    </div>
  );
}
