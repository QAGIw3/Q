import React, { useState, useEffect, useCallback, useContext } from 'react';
import ReactFlow, { addEdge, Connection, Edge, Node, Position } from 'reactflow';
import 'reactflow/dist/style.css';
import { AuthContext } from '../../AuthContext';
import dagre from 'dagre';

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 150, height: 50 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = isHorizontal ? Position.Left : Position.Top;
    node.sourcePosition = isHorizontal ? Position.Right : Position.Bottom;
    node.position = {
      x: nodeWithPosition.x - 150 / 2,
      y: nodeWithPosition.y - 50 / 2,
    };
    return node;
  });

  return { nodes, edges };
};


const WorkflowVisualizer: React.FC<{ workflowId: string }> = ({ workflowId }) => {
    const [nodes, setNodes] = useState<Node[]>([]);
    const [edges, setEdges] = useState<Edge[]>([]);
    const authContext = useContext(AuthContext);

    useEffect(() => {
        if (!authContext?.token) return;

        const ws = new WebSocket(`ws://localhost:8001/api/v1/dashboard/ws`);

        ws.onmessage = (event) => {
            const eventData = JSON.parse(event.data);
            if (eventData.workflow_id !== workflowId) return;

            setNodes((nds) => {
                const newNodes = [...nds];
                const existingNode = newNodes.find((n) => n.id === eventData.task_id);
                if (existingNode) {
                    existingNode.data = { ...existingNode.data, status: eventData.data.status };
                }
                return newNodes;
            });
        };

        return () => ws.close();
    }, [workflowId, authContext?.token]);
    
    // Placeholder for fetching initial workflow structure
    useEffect(() => {
        // In a real app, you would fetch the workflow structure here
        // and then generate the initial nodes and edges.
        const initialNodes: Node[] = [
            // This would be generated from the workflow data
        ];
        const initialEdges: Edge[] = [
            // This would be generated from the workflow dependencies
        ];

        const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
            initialNodes,
            initialEdges
        );

        setNodes(layoutedNodes);
        setEdges(layoutedEdges);
    }, [workflowId]);


    const onConnect = (params: Connection | Edge) => setEdges((eds) => addEdge(params, eds));

    return (
        <div style={{ height: '500px', border: '1px solid #ccc' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onConnect={onConnect}
                fitView
            >
            </ReactFlow>
        </div>
    );
};

export default WorkflowVisualizer; 