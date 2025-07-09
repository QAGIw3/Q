import React from 'react';

interface SemanticResult {
    id: string;
    text: string;
    score: number;
}

interface SemanticResultsProps {
    results: SemanticResult[];
}

export const SemanticResults: React.FC<SemanticResultsProps> = ({ results }) => {
    return (
        <div className="semantic-results-container">
            <h3>Semantic Search Results</h3>
            <ul>
                {results.map(result => (
                    <li key={result.id}>
                        <p>{result.text}</p>
                        <span>Score: {result.score.toFixed(2)}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}; 