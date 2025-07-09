// WebAppQ/app/src/pages/WorkflowStudioPage.tsx
import React from 'react';
import { Container, Typography } from '@mui/material';
import { WorkflowBuilder } from '../components/Workflows/WorkflowBuilder';

export const WorkflowStudioPage: React.FC = () => {
    return (
        <Container maxWidth="xl" sx={{ mt: 4, height: 'calc(100vh - 100px)' }}>
            <Typography variant="h4" gutterBottom>
                Workflow Studio
            </Typography>
            <Typography paragraph color="text.secondary">
                Design, build, and manage your automated workflows. Drag nodes from the sidebar onto the canvas to get started.
            </Typography>
            <WorkflowBuilder />
        </Container>
    );
}; 