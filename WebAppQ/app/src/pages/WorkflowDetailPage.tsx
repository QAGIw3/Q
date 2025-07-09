import React from 'react';
import { useParams } from 'react-router-dom';
import WorkflowVisualizer from '../components/WorkflowVisualizer/WorkflowVisualizer';
import { Link } from 'react-router-dom';

export const WorkflowDetailPage: React.FC = () => {
    const { workflowId } = useParams<{ workflowId: string }>();

    if (!workflowId) {
        return <div>Workflow ID not found.</div>;
    }

    return (
        <div style={{ padding: '20px' }}>
            <Link to="/workflows">&larr; Back to Workflows</Link>
            <h1>Workflow Details</h1>
            <WorkflowVisualizer workflowId={workflowId} />
        </div>
    );
}; 