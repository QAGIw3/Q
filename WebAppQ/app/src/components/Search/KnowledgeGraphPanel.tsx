import React from 'react';
import { KnowledgeGraphResult, KGNode } from '../../services/types';

interface KnowledgeGraphPanelProps {
    graph: KnowledgeGraphResult | null;
}

const renderNode = (node: KGNode) => {
    const type = node.properties?.type || 'Entity';
    return <li key={node.id}>{node.label} ({type})</li>;
}

export const KnowledgeGraphPanel: React.FC<KnowledgeGraphPanelProps> = ({ graph }) => {
    if (!graph || graph.nodes.length === 0) {
        return (
            <div className="kg-panel-container">
                <h3>Knowledge Graph</h3>
                <p>No graph results found.</p>
            </div>
        );
    }
    
    return (
        <div className="kg-panel-container">
            <h3>Knowledge Graph</h3>
            <h4>Nodes</h4>
            <ul>
                {graph.nodes.map(renderNode)}
            </ul>
            <h4>Edges</h4>
            <ul>
                {graph.edges.map(edge => <li key={`${edge.source}-${edge.target}`}>{edge.source} &rarr; {edge.target} ({edge.label})</li>)}
            </ul>
        </div>
    );
}; 