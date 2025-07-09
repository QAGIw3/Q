import React from 'react';

interface AISummaryProps {
    summary: string | null;
}

export const AISummary: React.FC<AISummaryProps> = ({ summary }) => {
    if (!summary) {
        return null;
    }
    
    return (
        <div className="ai-summary-container">
            <h3>AI-Generated Summary</h3>
            <p>{summary}</p>
        </div>
    );
}; 