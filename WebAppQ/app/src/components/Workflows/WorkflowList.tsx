import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listWorkflows, connectToDashboardSocket, disconnectFromDashboardSocket } from '../../services/managerAPI';
import './Workflows.css';

// Define a more specific type for a workflow object
interface Workflow {
    workflow_id: string;
    original_prompt: string;
    status: string;
    created_at: string;
}

export const WorkflowList: React.FC = () => {
    const [workflows, setWorkflows] = useState<Workflow[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchWorkflows = async () => {
            try {
                const fetchedWorkflows = await listWorkflows();
                setWorkflows(fetchedWorkflows);
            } catch (err: any) {
                setError(err.message || 'Failed to fetch workflows.');
            } finally {
                setIsLoading(false);
            }
        };

        fetchWorkflows();

        // Connect to WebSocket for real-time updates
        connectToDashboardSocket((message: any) => {
            if (message.event_type === 'WORKFLOW_COMPLETED' || message.event_type === 'TASK_STATUS_UPDATE') {
                // A simple way to update is to re-fetch the list.
                // A more optimized way would be to find and update the specific workflow in the list.
                fetchWorkflows();
            }
        });

        return () => {
            disconnectFromDashboardSocket();
        };

    }, []);

    if (isLoading) {
        return <div>Loading workflows...</div>;
    }

    if (error) {
        return <div className="error-message">{error}</div>;
    }

    return (
        <div className="workflow-list-container">
            <h3>All Workflows</h3>
            <ul className="workflow-list">
                {workflows.map(wf => (
                    <li key={wf.workflow_id} className={`workflow-item status-${wf.status.toLowerCase()}`}>
                        <Link to={`/workflows/${wf.workflow_id}`}>
                            <div className="workflow-item-prompt">{wf.original_prompt}</div>
                            <div className="workflow-item-details">
                                <span>{wf.workflow_id}</span>
                                <span className="workflow-status">{wf.status}</span>
                                <span>{new Date(wf.created_at).toLocaleString()}</span>
                            </div>
                        </Link>
                    </li>
                ))}
            </ul>
        </div>
    );
}; 