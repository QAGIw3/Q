import React from 'react';

interface GraphNode {
    id: string;
    label: string;
    type: string;
}

interface GraphEdge {
    from: string;
    to: string;
    label: string;
}

interface KnowledgeGraphPanelProps {
    graph: {
        nodes: GraphNode[];
        edges: GraphEdge[];
    };
}

export const KnowledgeGraphPanel: React.FC<KnowledgeGraphPanelProps> = ({ graph }) => {
    return (
        <div className="kg-panel-container">
            <h3>Knowledge Graph</h3>
            <h4>Nodes</h4>
            <ul>
                {graph.nodes.map(node => <li key={node.id}>{node.label} ({node.type})</li>)}
            </ul>
            <h4>Edges</h4>
            <ul>
                {graph.edges.map(edge => <li key={`${edge.from}-${edge.to}`}>{edge.from} &rarr; {edge.to} ({edge.label})</li>)}
            </ul>
        </div>
    );
}; 