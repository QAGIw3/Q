// WebAppQ/app/src/pages/ApprovalsPage.tsx
import React, { useState, useEffect, useContext } from 'react';
import { Container, Typography } from '@mui/material';
import { ApprovalCard } from '../components/Workflows/ApprovalCard';
import { AuthContext } from '../AuthContext';
import { connectToDashboardSocket, disconnectFromDashboardSocket, respondToApproval } from '../services/managerAPI';

interface ApprovalRequest {
    workflow_id: string;
    task_id: string;
    message: string;
}

export const ApprovalsPage: React.FC = () => {
    const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
    const authContext = useContext(AuthContext);

    useEffect(() => {
        // Function to handle incoming WebSocket messages
        const handleSocketMessage = (data: any) => {
            if (data.event_type === "APPROVAL_REQUIRED") {
                setApprovals(prev => {
                    // Avoid adding duplicates
                    if (prev.find(a => a.task_id === data.task_id)) {
                        return prev;
                    }
                    return [...prev, data];
                });
            }
        };

        if (authContext?.isAuthenticated) {
            connectToDashboardSocket(handleSocketMessage);
        }

        // Cleanup on component unmount
        return () => {
            disconnectFromDashboardSocket();
        };
    }, [authContext]);

    const handleApprovalResponse = async (workflowId: string, taskId: string, approved: boolean) => {
        try {
            await respondToApproval(workflowId, taskId, approved);
            // Remove the card from the list upon successful response
            setApprovals(prev => prev.filter(a => a.task_id !== taskId));
        } catch (error) {
            console.error("Failed to respond to approval:", error);
            // Optionally show an error message to the user
        }
    };

    return (
        <Container>
            <Typography variant="h4" sx={{ my: 4 }}>
                Pending Approvals
            </Typography>
            {approvals.length === 0 ? (
                <Typography>No pending approvals.</Typography>
            ) : (
                approvals.map(approval => (
                    <ApprovalCard
                        key={approval.task_id}
                        workflowId={approval.workflow_id}
                        taskId={approval.task_id}
                        message={approval.message}
                        onApprove={() => handleApprovalResponse(approval.workflow_id, approval.task_id, true)}
                        onReject={() => handleApprovalResponse(approval.workflow_id, approval.task_id, false)}
                    />
                ))
            )}
        </Container>
    );
}; 