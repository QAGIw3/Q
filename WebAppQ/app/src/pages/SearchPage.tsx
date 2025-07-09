import React, { useState } from 'react';
import { cognitiveSearch } from 'services/managerAPI';
import { SearchBar } from 'components/Search/SearchBar';
import { AISummary } from 'components/Search/AISummary';
import { SemanticResults } from 'components/Search/SemanticResults';
import { KnowledgeGraphPanel } from 'components/Search/KnowledgeGraphPanel';

export const SearchPage: React.FC = () => {
    const [results, setResults] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSearch = async (query: string) => {
        if (!query.trim()) return;
        
        setIsLoading(true);
        setError(null);
        setResults(null);

        try {
            const searchResults = await cognitiveSearch(query);
            setResults(searchResults);
        } catch (err: any) {
            setError(err.message || 'An unknown error occurred.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div style={{ padding: '20px' }}>
            <h1>Cognitive Search</h1>
            <SearchBar onSearch={handleSearch} isLoading={isLoading} />
            
            {isLoading && <div style={{ marginTop: '20px' }}>Loading...</div>}
            {error && <div style={{ marginTop: '20px', color: 'red' }}>{error}</div>}

            {results && (
                <div style={{ display: 'flex', gap: '20px', marginTop: '20px' }}>
                    <div style={{ flex: 2 }}>
                        <AISummary summary={results.summary} />
                        <SemanticResults results={results.semantic_results} />
                    </div>
                    <div style={{ flex: 1 }}>
                        <KnowledgeGraphPanel graph={results.graph_results} />
                    </div>
                </div>
            )}
        </div>
    );
}; 