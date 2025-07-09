import React, { useState, useEffect, useCallback, useContext } from 'react';
import ReactFlow, { addEdge, Connection, Edge, Node, Position, Handle } from 'reactflow';
import 'reactflow/dist/style.css';
import './WorkflowVisualizer.css';
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

const workflowToElements = (workflow: any): { nodes: Node[], edges: Edge[] } => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const workflowId = workflow.workflow_id;

    const traverse = (tasks: any[], parentId?: string) => {
        tasks.forEach(task => {
            let nodeType = 'default';
            if (task.type === 'approval') nodeType = 'approval';
            if (task.type === 'conditional') nodeType = 'default';

            nodes.push({
                id: task.task_id,
                data: { 
                    label: `${task.type}: ${task.task_id.substring(0, 8)}`, 
                    status: task.status,
                    message: task.message, // For approval nodes
                    workflowId: workflowId,
                },
                position: { x: 0, y: 0 },
                type: nodeType,
                className: `status-${task.status}`
            });
            if (parentId) {
                edges.push({ id: `e-${parentId}-${task.task_id}`, source: parentId, target: task.task_id, animated: true });
            }
            if (task.dependencies && task.dependencies.length > 0) {
                task.dependencies.forEach((dep: string) => {
                    edges.push({ id: `e-${dep}-${task.task_id}`, source: dep, target: task.task_id });
                });
            }
            if (task.type === 'conditional') {
                task.branches.forEach((branch: any) => {
                    traverse(branch.tasks, task.task_id);
                });
            }
        });
    };

    traverse(workflow.tasks);
    return { nodes, edges };
};

const ApprovalNode = ({ data }: { data: any }) => {
    const handleApproval = async (approved: boolean) => {
        const { workflowId, label } = data;
        const taskId = label.split(': ')[1];
        
        // This is a simplified way to get the token. A better approach would be to use a context or a dedicated hook.
        const token = localStorage.getItem('react-token'); 
        
        await fetch(`http://localhost:8001/api/v1/workflows/${workflowId}/tasks/${taskId}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ approved }),
        });
    };

    return (
        <div className="approval-node">
            <Handle type="target" position={Position.Top} />
            <div>{data.message}</div>
            {data.status === 'pending_approval' && (
                <div className="approval-buttons">
                    <button onClick={() => handleApproval(true)}>Approve</button>
                    <button onClick={() => handleApproval(false)}>Reject</button>
                </div>
            )}
            <Handle type="source" position={Position.Bottom} />
        </div>
    );
};

const nodeTypes = {
    approval: ApprovalNode,
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
    
    useEffect(() => {
        if (!authContext?.token || !workflowId) return;

        const fetchWorkflow = async () => {
            try {
                const response = await fetch(`http://localhost:8001/api/v1/workflows/${workflowId}`, {
                    headers: { 'Authorization': `Bearer ${authContext.token}` }
                });
                if (!response.ok) throw new Error('Failed to fetch workflow');
                const workflowData = await response.json();
                
                const { nodes: initialNodes, edges: initialEdges } = workflowToElements(workflowData);
                const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                    initialNodes,
                    initialEdges
                );
                setNodes(layoutedNodes);
                setEdges(layoutedEdges);
            } catch (error) {
                console.error("Error fetching workflow:", error);
            }
        };

        fetchWorkflow();
    }, [workflowId, authContext?.token]);


    const onConnect = (params: Connection | Edge) => setEdges((eds) => addEdge(params, eds));

    return (
        <div style={{ height: '500px', border: '1px solid #ccc' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onConnect={onConnect}
                fitView
                nodeTypes={nodeTypes}
            >
            </ReactFlow>
        </div>
    );
};

export default WorkflowVisualizer; 