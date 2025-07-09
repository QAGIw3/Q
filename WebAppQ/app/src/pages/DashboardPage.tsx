// WebAppQ/app/src/pages/DashboardPage.tsx
import React from 'react';
import { Container, Typography, Grid, Paper } from '@mui/material';
import { ActiveWorkflowsWidget } from '../components/Dashboard/ActiveWorkflowsWidget';

const AgentPerformanceWidget = () => <Paper sx={{p: 2, height: '100%'}}>Agent Performance Widget</Paper>;
const ModelTestsWidget = () => <Paper sx={{p: 2, height: '100%'}}>Model A/B Tests Widget</Paper>;

export const DashboardPage: React.FC = () => {
    return (
        <Container maxWidth="xl" sx={{ mt: 4 }}>
            <Typography variant="h4" gutterBottom>
                Observability Dashboard
            </Typography>
            <Grid container spacing={3}>
                <Grid xs={12} md={8}>
                    <ActiveWorkflowsWidget />
                </Grid>
                <Grid xs={12} md={4}>
                    <AgentPerformanceWidget />
                </Grid>
                <Grid xs={12}>
                    <ModelTestsWidget />
                </Grid>
            </Grid>
        </Container>
    );
}; 