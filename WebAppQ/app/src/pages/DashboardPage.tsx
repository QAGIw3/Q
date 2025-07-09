// WebAppQ/app/src/pages/DashboardPage.tsx
import React from 'react';
import { Container, Typography, Grid, Paper } from '@mui/material';
import { ActiveWorkflowsWidget } from '../components/Dashboard/ActiveWorkflowsWidget';
import { AgentPerformanceWidget } from '../components/Dashboard/AgentPerformanceWidget';
import { ModelTestsWidget } from '../components/Dashboard/ModelTestsWidget';

export const DashboardPage: React.FC = () => {
    return (
        <Container maxWidth="xl" sx={{ mt: 4 }}>
            <Typography variant="h4" gutterBottom>
                Observability Dashboard
            </Typography>
            <Grid container spacing={3}>
                <Grid item>
                    <ActiveWorkflowsWidget />
                </Grid>
                <Grid item>
                    <AgentPerformanceWidget />
                </Grid>
                <Grid item>
                    <ModelTestsWidget />
                </Grid>
            </Grid>
        </Container>
    );
}; 