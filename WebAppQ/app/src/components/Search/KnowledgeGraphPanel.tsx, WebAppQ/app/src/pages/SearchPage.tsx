import { GraphDetailPanel } from './GraphDetailPanel';

export const KnowledgeGraphPanel: React.FC<KnowledgeGraphPanelProps> = ({ graph }) => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);

    // ... (useEffect and onNodeClick are the same)

    const onNodeClick = (event: React.MouseEvent, node: Node) => {
        setSelectedNode(node);
        // ... (existing neighbor fetching logic)
    };
    
    // ...
    return (
        <div style={{ display: 'flex', height: '500px' }}>
            <div className="kg-panel-container" style={{ flex: 3, border: '1px solid #ddd' }}>
                <ReactFlow ... onNodeClick={onNodeClick} ... />
            </div>
            <div style={{ flex: 1, marginLeft: '10px' }}>
                <GraphDetailPanel selectedNode={selectedNode} />
            </div>
        </div>
    );
}; 