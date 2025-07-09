import React from 'react';
import { VectorStoreResult } from '../../services/types';

interface SemanticResultsProps {
    results: VectorStoreResult[];
}

export const SemanticResults: React.FC<SemanticResultsProps> = ({ results }) => {
    if (!results || results.length === 0) {
        return <p>No semantic results found.</p>;
    }
    
    return (
        <div className="semantic-results-container">
            <h3>Semantic Search Results</h3>
            <ul>
                {results.map((result, index) => (
                    <li key={`${result.source}-${index}`}>
                        <p><strong>Source:</strong> {result.source}</p>
                        <p>{result.content}</p>
                        <span>Score: {result.score.toFixed(2)}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}; 