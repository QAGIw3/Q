// WebAppQ/app/src/components/common/FeedbackBox.tsx
import React, { useState } from 'react';
import { submitFeedback } from '../../services/h2mAPI';

interface FeedbackBoxProps {
    reference_id: string; // ID of the item being rated (e.g., summary ID, message ID)
    context: string; // The context of the feedback (e.g., "AISummary")
    prompt?: string;
    model_version?: string;
}

export const FeedbackBox: React.FC<FeedbackBoxProps> = ({ reference_id, context, prompt, model_version }) => {
    const [submitted, setSubmitted] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const handleFeedback = async (score: number) => {
        try {
            await submitFeedback({ reference_id, context, score, prompt, model_version });
            setSubmitted(true);
            setError(null);
        } catch (err: any) {
            setError(err.message || "Failed to submit feedback.");
        }
    };

    if (submitted) {
        return <div className="feedback-box">Thank you for your feedback!</div>;
    }

    if (error) {
        return <div className="feedback-box" style={{ color: 'red' }}>{error}</div>;
    }

    return (
        <div className="feedback-box" style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span>Was this helpful?</span>
            <button onClick={() => handleFeedback(1)} title="Helpful">👍</button>
            <button onClick={() => handleFeedback(-1)} title="Not Helpful">👎</button>
        </div>
    );
}; 