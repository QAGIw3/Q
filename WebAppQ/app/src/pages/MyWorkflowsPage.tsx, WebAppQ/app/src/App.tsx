import React, { useState, useEffect } from 'react';
import { Container, Typography, List, ListItem, ListItemText, IconButton, ListItemSecondaryAction, Button } from '@mui/material';
import { Link } from 'react-router-dom';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { listWorkflows } from '../services/workflowBuilderAPI';
import { Workflow } from '../services/types';

export const MyWorkflowsPage: React.FC = () => {
    const [workflows, setWorkflows] = useState<Workflow[]>([]);
    
    useEffect(() => {
        listWorkflows().then(setWorkflows).catch(console.error);
    }, []);

    const handleRunWorkflow = async (workflowId: string) => {
        alert(`Running workflow ${workflowId}`);
    };

    return (
        <Container>
            <Typography variant="h4" sx={{ my: 4 }}>My Workflows</Typography>
            <Button component={Link} to="/studio" variant="contained" sx={{ mb: 2 }}>
                Create New Workflow
            </Button>
            <List>
                {workflows.map(wf => (
                    <ListItem key={wf.workflow_id}>
                        <ListItemText primary={wf.original_prompt} secondary={`ID: ${wf.workflow_id}`} />
                        <ListItemSecondaryAction>
                            <IconButton edge="end" aria-label="run" onClick={() => handleRunWorkflow(wf.workflow_id)}>
                                <PlayArrowIcon />
                            </IconButton>
                        </ListItemSecondaryAction>
                    </ListItem>
                ))}
            </List>
        </Container>
    );
}; 