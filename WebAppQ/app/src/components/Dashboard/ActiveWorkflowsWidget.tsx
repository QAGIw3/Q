// WebAppQ/app/src/components/Dashboard/ActiveWorkflowsWidget.tsx
import React, { useState, useEffect } from 'react';
import { Paper, Typography, List, ListItem, ListItemText, Chip } from '@mui/material';
import { Workflow } from '../../services/types';
import { connectToObservabilitySocket } from './shared';

export const ActiveWorkflowsWidget: React.FC = () => {
    const [workflows, setWorkflows] = useState<Record<string, Workflow>>({});

    useEffect(() => {
        const socket = connectToObservabilitySocket((data) => {
            if (data.type === 'WORKFLOW_UPDATE') {
                const workflow = data.payload as Workflow;
                setWorkflows(prev => ({
                    ...prev,
                    [workflow.workflow_id]: workflow
                }));
            }
        });

        return () => {
            socket.close();
        };
    }, []);

    const runningWorkflows = Object.values(workflows).filter(wf => wf.status === 'RUNNING');

    return (
        <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Active Workflows</Typography>
            <List>
                {runningWorkflows.length === 0 && <ListItem><ListItemText primary="No active workflows." /></ListItem>}
                {runningWorkflows.map(wf => (
                    <ListItem key={wf.workflow_id}>
                        <ListItemText 
                            primary={wf.original_prompt}
                            secondary={`ID: ${wf.workflow_id}`}
                        />
                        <Chip label={wf.status} color="primary" size="small" />
                    </ListItem>
                ))}
            </List>
        </Paper>
    );
}; 