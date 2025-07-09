// WebAppQ/app/src/components/Workflows/ApprovalCard.tsx
import React from 'react';
import { Card, CardContent, Typography, Button, Box } from '@mui/material';

interface ApprovalCardProps {
    workflowId: string;
    taskId: string;
    message: string;
    onApprove: (workflowId: string, taskId: string) => void;
    onReject: (workflowId: string, taskId: string) => void;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({ workflowId, taskId, message, onApprove, onReject }) => {
    return (
        <Card sx={{ mb: 2 }}>
            <CardContent>
                <Typography variant="h6" gutterBottom>
                    Approval Required
                </Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                    {message}
                </Typography>
                <Typography variant="caption" display="block" color="text.secondary">
                    Workflow: {workflowId} | Task: {taskId}
                </Typography>
                <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                    <Button variant="outlined" color="error" onClick={() => onReject(workflowId, taskId)} sx={{ mr: 1 }}>
                        Reject
                    </Button>
                    <Button variant="contained" color="success" onClick={() => onApprove(workflowId, taskId)}>
                        Approve
                    </Button>
                </Box>
            </CardContent>
        </Card>
    );
}; 