// WebAppQ/app/src/services/types.ts

export interface SearchQuery {
    query: string;
    session_id?: string;
}

export interface VectorStoreResult {
    source: string;
    content: string;
    score: number;
    metadata: Record<string, any>;
}

export interface KGNode {
    id: string;
    label: string;
    properties: Record<string, any>;
}

export interface KGEdge {
    source: string;
    target: string;
    label: string;
}

export interface KnowledgeGraphResult {
    nodes: KGNode[];
    edges: KGEdge[];
}

export interface SearchResponse {
    ai_summary: string | null;
    vector_results: VectorStoreResult[];
    knowledge_graph_result: KnowledgeGraphResult | null;
}

export interface FeedbackEvent {
    reference_id: string;
    context: string;
    score: number;
    prompt?: string;
    feedback_text?: string;
}

export interface UserCreate {
    username: string;
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
} 