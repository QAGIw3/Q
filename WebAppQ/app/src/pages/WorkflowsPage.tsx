import React, { useState } from 'react';
import { CreateWorkflowForm } from '../components/Workflows/CreateWorkflowForm';
import { WorkflowList } from '../components/Workflows/WorkflowList';

export const WorkflowsPage: React.FC = () => {
    // This state is used to trigger a re-render of the WorkflowList when a new workflow is created.
    const [_, setLastCreatedWorkflow] = useState<any>(null);

    const handleWorkflowCreated = (workflow: any) => {
        setLastCreatedWorkflow(workflow);
    };

    return (
        <div style={{ padding: '20px' }}>
            <h1>Workflows</h1>
            <CreateWorkflowForm onWorkflowCreated={handleWorkflowCreated} />
            <WorkflowList />
        </div>
    );
}; 