// WebAppQ/app/src/components/Dashboard/AgentPerformanceWidget.tsx
import React, { useState, useEffect } from 'react';
import { Paper, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import { connectToObservabilitySocket } from './shared';

interface AgentStats {
    total_tasks: number;
    successful_tasks: number;
    total_execution_time_ms: number;
}

export const AgentPerformanceWidget: React.FC = () => {
    const [agentPerformance, setAgentPerformance] = useState<Record<string, AgentStats>>({});

    useEffect(() => {
        const socket = connectToObservabilitySocket((data) => {
            if (data.type === 'AGENT_PERFORMANCE_METRIC') {
                const { agent_id, status, execution_time_ms } = data.payload;
                
                setAgentPerformance(prev => {
                    const currentStats = prev[agent_id] || { total_tasks: 0, successful_tasks: 0, total_execution_time_ms: 0 };
                    return {
                        ...prev,
                        [agent_id]: {
                            total_tasks: currentStats.total_tasks + 1,
                            successful_tasks: currentStats.successful_tasks + (status === 'COMPLETED' ? 1 : 0),
                            total_execution_time_ms: currentStats.total_execution_time_ms + (execution_time_ms || 0)
                        }
                    };
                });
            }
        });

        return () => socket.close();
    }, []);

    return (
        <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>Agent Performance</Typography>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>Agent</TableCell>
                            <TableCell>Success Rate</TableCell>
                            <TableCell>Avg. Time (ms)</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {Object.entries(agentPerformance).map(([agentId, stats]) => (
                            <TableRow key={agentId}>
                                <TableCell>{agentId}</TableCell>
                                <TableCell>
                                    {stats.total_tasks > 0 ? `${((stats.successful_tasks / stats.total_tasks) * 100).toFixed(0)}%` : 'N/A'}
                                </TableCell>
                                <TableCell>
                                    {stats.successful_tasks > 0 ? (stats.total_execution_time_ms / stats.successful_tasks).toFixed(2) : 'N/A'}
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
}; 