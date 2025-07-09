import React from 'react';

interface AISummaryProps {
    summary: string;
}

export const AISummary: React.FC<AISummaryProps> = ({ summary }) => {
    return (
        <div className="ai-summary-container">
            <h3>AI-Generated Summary</h3>
            <p>{summary}</p>
        </div>
    );
}; 