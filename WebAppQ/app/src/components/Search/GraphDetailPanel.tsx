// WebAppQ/app/src/components/Search/GraphDetailPanel.tsx
import React from 'react';
import { Card, CardContent, Typography, Box } from '@mui/material';
import { Node } from 'reactflow';

interface GraphDetailPanelProps {
    selectedNode: Node | null;
}

export const GraphDetailPanel: React.FC<GraphDetailPanelProps> = ({ selectedNode }) => {
    if (!selectedNode) {
        return (
            <Card>
                <CardContent>
                    <Typography color="text.secondary">Select a node to see details</Typography>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardContent>
                <Typography variant="h6" gutterBottom>
                    {selectedNode.data.label}
                </Typography>
                <Box>
                    <Typography variant="subtitle2">Properties:</Typography>
                    <pre style={{ background: '#f5f5f5', padding: '10px', borderRadius: '4px' }}>
                        {JSON.stringify(selectedNode.data.properties, null, 2)}
                    </pre>
                </Box>
            </CardContent>
        </Card>
    );
}; 