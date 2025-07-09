import React, { useState } from 'react';
import { createWorkflow } from '../../services/managerAPI';
import './Workflows.css';

interface CreateWorkflowFormProps {
    onWorkflowCreated: (workflow: any) => void;
}

export const CreateWorkflowForm: React.FC<CreateWorkflowFormProps> = ({ onWorkflowCreated }) => {
    const [prompt, setPrompt] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        if (!prompt.trim()) {
            setError('Prompt cannot be empty.');
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const newWorkflow = await createWorkflow(prompt);
            onWorkflowCreated(newWorkflow);
            setPrompt(''); // Clear form on success
        } catch (err: any) {
            setError(err.message || 'An unknown error occurred.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="create-workflow-form-container">
            <h3>Create a New Workflow</h3>
            <form onSubmit={handleSubmit}>
                <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Enter a high-level goal for the new workflow..."
                    rows={4}
                    disabled={isLoading}
                />
                <button type="submit" disabled={isLoading}>
                    {isLoading ? 'Creating...' : 'Create Workflow'}
                </button>
                {error && <p className="error-message">{error}</p>}
            </form>
        </div>
    );
}; 