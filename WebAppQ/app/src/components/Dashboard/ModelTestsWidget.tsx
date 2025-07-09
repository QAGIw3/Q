// WebAppQ/app/src/components/Dashboard/ModelTestsWidget.tsx
import React, { useState, useEffect } from 'react';
import { Paper, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import { connectToObservabilitySocket } from './shared';

interface ModelStats {
    positive_feedback: number;
    negative_feedback: number;
    total_feedback: number;
}

export const ModelTestsWidget: React.FC = () => {
    const [modelPerformance, setModelPerformance] = useState<Record<string, ModelStats>>({});

    useEffect(() => {
        const socket = connectToObservabilitySocket((data) => {
            if (data.type === 'MODEL_A/B_TEST_UPDATE') {
                const { model_version, score } = data.payload;
                
                setModelPerformance(prev => {
                    const currentStats = prev[model_version] || { positive_feedback: 0, negative_feedback: 0, total_feedback: 0 };
                    return {
                        ...prev,
                        [model_version]: {
                            total_feedback: currentStats.total_feedback + 1,
                            positive_feedback: currentStats.positive_feedback + (score > 0 ? 1 : 0),
                            negative_feedback: currentStats.negative_feedback + (score < 0 ? 1 : 0)
                        }
                    };
                });
            }
        });

        return () => socket.close();
    }, []);

    return (
        <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Model A/B Test Performance</Typography>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>Model Version</TableCell>
                            <TableCell>Positive Feedback</TableCell>
                            <TableCell>Negative Feedback</TableCell>
                            <TableCell>Win Rate</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {Object.entries(modelPerformance).map(([modelVersion, stats]) => (
                            <TableRow key={modelVersion}>
                                <TableCell>{modelVersion}</TableCell>
                                <TableCell>{stats.positive_feedback}</TableCell>
                                <TableCell>{stats.negative_feedback}</TableCell>
                                <TableCell>
                                    {stats.total_feedback > 0 ? `${((stats.positive_feedback / stats.total_feedback) * 100).toFixed(0)}%` : 'N/A'}
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
}; 