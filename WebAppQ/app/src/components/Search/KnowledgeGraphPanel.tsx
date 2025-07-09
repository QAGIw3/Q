import React, { useState, useEffect } from 'react';
import ReactFlow, { MiniMap, Controls, Background, Node, Edge, useNodesState, useEdgesState } from 'reactflow';
import 'reactflow/dist/style.css';
import { produce } from 'immer';
import ELK from 'elkjs/lib/elk.bundled.js';

import { KnowledgeGraphResult } from '../../services/types';
import { getNodeNeighbors } from '../../services/managerAPI';
import { GraphDetailPanel } from './GraphDetailPanel';

interface KnowledgeGraphPanelProps {
    graph: KnowledgeGraphResult | null;
}

const position = { x: 0, y: 0 };

const transformDataForFlow = (graphData: KnowledgeGraphResult): { nodes: Node[], edges: Edge[] } => {
    const nodes: Node[] = graphData.nodes.map((node, i) => ({
        id: node.id,
        data: { label: `${node.label}: ${node.properties.name || node.id}` },
        position: { x: i * 250, y: (i % 2) * 100 } // Simple layout logic
    }));

    const edges: Edge[] = graphData.edges.map(edge => ({
        id: `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        animated: true
    }));

    return { nodes, edges };
};

const elk = new ELK();

const getLayoutedElements = (nodes: Node[], edges: Edge[]): Promise<{ nodes: Node[], edges: Edge[] }> => {
    const elkNodes: any[] = nodes.map(node => {
        const { id, ...rest } = node;
        return { id, width: 150, height: 50, ...rest };
    });

    const elkEdges: any[] = edges.map(edge => ({
        id: edge.id,
        sources: [edge.source],
        targets: [edge.target]
    }));

    const graph = {
        id: 'root',
        layoutOptions: { 'elk.algorithm': 'layered' },
        children: elkNodes,
        edges: elkEdges,
    };

    return elk.layout(graph)
        .then((layoutedGraph: any) => ({
            nodes: layoutedGraph.children.map((node: any) => ({
                ...node,
                position: { x: node.x, y: node.y },
            })),
            edges: layoutedGraph.edges.map((edge: any) => ({
                id: edge.id,
                source: edge.sources[0],
                target: edge.targets[0],
                ...edge.properties, // Pass through other edge properties
            })),
        }))
        .catch(error => {
            console.error("ELK layout failed:", error);
            return { nodes: [], edges: [] };
        });
};


export const KnowledgeGraphPanel: React.FC<KnowledgeGraphPanelProps> = ({ graph }) => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);

    useEffect(() => {
        if (graph) {
            const { nodes: initialNodes, edges: initialEdges } = transformDataForFlow(graph);
            getLayoutedElements(initialNodes, initialEdges).then(layout => {
                if (layout) {
                    setNodes(layout.nodes);
                    setEdges(layout.edges);
                }
            });
        }
    }, [graph, setNodes, setEdges]);

    const onNodeClick = async (event: React.MouseEvent, node: Node) => {
        setSelectedNode(node);
        try {
            const newGraphData = await getNodeNeighbors(node.id);
            const { nodes: newNodes, edges: newEdges } = transformDataForFlow(newGraphData);

            setNodes(currentNodes => produce(currentNodes, draft => {
                newNodes.forEach(newNode => {
                    if (!draft.find(n => n.id === newNode.id)) {
                        draft.push(newNode);
                    }
                });
            }));

            setEdges(currentEdges => produce(currentEdges, draft => {
                newEdges.forEach(newEdge => {
                    if (!draft.find(e => e.id === newEdge.id)) {
                        draft.push(newEdge);
                    }
                });
            }));
        } catch (error) {
            console.error("Failed to fetch neighbors:", error);
        }
    };
    
    return (
        <div style={{ display: 'flex', height: '500px' }}>
            <div className="kg-panel-container" style={{ flex: 3, border: '1px solid #ddd' }}>
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onNodeClick={onNodeClick}
                    fitView
                >
                    <Controls />
                    <MiniMap />
                    <Background gap={12} size={1} />
                </ReactFlow>
            </div>
            <div style={{ flex: 1, marginLeft: '10px' }}>
                <GraphDetailPanel selectedNode={selectedNode} />
            </div>
        </div>
    );
}; 