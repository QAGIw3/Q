// WebAppQ/app/src/components/Workflows/WorkflowBuilder.tsx
import React, { useState, useCallback } from 'react';
import ReactFlow, {
  ReactFlowProvider,
  addEdge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  Connection,
  Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { saveWorkflow } from '../../services/workflowBuilderAPI';
import { Workflow, WorkflowTask, ApprovalBlock } from '../../services/types';
import { Node } from 'reactflow';

const initialNodes = [
  { id: '1', type: 'input', data: { label: 'Start' }, position: { x: 250, y: 5 } },
];

const Sidebar = () => {
    const onDragStart = (event: React.DragEvent, nodeType: string) => {
        event.dataTransfer.setData('application/reactflow', nodeType);
        event.dataTransfer.effectAllowed = 'move';
    };

    return (
        <aside style={{ borderRight: '1px solid #eee', padding: '15px', fontSize: '12px' }}>
            <div className="description">You can drag these nodes to the pane on the right.</div>
            <div className="dndnode" onDragStart={(event) => onDragStart(event, 'default')} draggable>
                Task Node
            </div>
            <div className="dndnode dndnode-output" onDragStart={(event) => onDragStart(event, 'output')} draggable>
                Approval Node
            </div>
        </aside>
    );
};

let id = 2;
const getId = () => `${id++}`;

const transformFlowToWorkflow = (nodes: Node[], edges: Edge[]): Partial<Workflow> => {
    const tasks: (WorkflowTask | ApprovalBlock)[] = nodes
        .filter(node => node.type !== 'input') // Exclude the 'Start' node
        .map(node => {
            const dependencies = edges.filter(edge => edge.target === node.id).map(edge => edge.source);
            if (node.type === 'output') { // Approval Node
                return {
                    task_id: node.id,
                    type: 'approval',
                    message: node.data.label,
                    required_roles: [],
                    dependencies: dependencies,
                };
            }
            return { // Default Task Node
                task_id: node.id,
                type: 'task',
                agent_personality: 'default', // Placeholder
                prompt: node.data.label,
                dependencies: dependencies,
            };
        });

    return {
        original_prompt: "User-created workflow",
        tasks: tasks,
        shared_context: {},
    };
};

export const WorkflowBuilder: React.FC = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);

    const onConnect = useCallback((params: Edge | Connection) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

    const onDragOver = useCallback((event: React.DragEvent) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = useCallback(
        (event: React.DragEvent) => {
            event.preventDefault();

            const type = event.dataTransfer.getData('application/reactflow');
            if (typeof type === 'undefined' || !type) {
                return;
            }

            const position = reactFlowInstance.screenToFlowPosition({
                x: event.clientX,
                y: event.clientY,
            });
            const newNode = {
                id: getId(),
                type,
                position,
                data: { label: `${type} node` },
            };

            setNodes((nds) => nds.concat(newNode));
        },
        [reactFlowInstance, setNodes],
    );

    const onSave = async () => {
        const workflowPayload = transformFlowToWorkflow(nodes, edges);
        try {
            await saveWorkflow(workflowPayload);
            alert('Workflow saved successfully!');
        } catch (error) {
            console.error(error);
            alert('Failed to save workflow.');
        }
    };
    
    return (
        <div className="dndflow" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ padding: '10px', textAlign: 'right' }}>
                <button onClick={onSave}>Save Workflow</button>
            </div>
            <ReactFlowProvider>
                <Sidebar />
                <div className="reactflow-wrapper" style={{ flexGrow: 1, height: '70vh' }}>
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        onInit={setReactFlowInstance}
                        onDrop={onDrop}
                        onDragOver={onDragOver}
                        fitView
                    >
                        <Controls />
                        <Background />
                    </ReactFlow>
                </div>
            </ReactFlowProvider>
        </div>
    );
}; 