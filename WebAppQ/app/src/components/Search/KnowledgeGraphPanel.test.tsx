// WebAppQ/app/src/components/Search/KnowledgeGraphPanel.test.tsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { KnowledgeGraphPanel } from './KnowledgeGraphPanel';
import { KnowledgeGraphResult } from '../../services/types';

describe('KnowledgeGraphPanel', () => {
  const mockGraph: KnowledgeGraphResult = {
    nodes: [
      { id: 'node1', label: 'Service A', properties: { type: 'Service' } },
      { id: 'node2', label: 'Database B', properties: { type: 'Database' } },
    ],
    edges: [
      { source: 'node1', target: 'node2', label: 'DEPENDS_ON' },
    ],
  };

  it('renders nodes and edges correctly when graph data is provided', () => {
    render(<KnowledgeGraphPanel graph={mockGraph} />);
    
    // Check for nodes
    expect(screen.getByText('Service A (Service)')).toBeInTheDocument();
    expect(screen.getByText('Database B (Database)')).toBeInTheDocument();

    // Check for edges
    const edge = screen.getByText(/node1.*node2/);
    expect(edge).toBeInTheDocument();
    expect(edge).toHaveTextContent('DEPENDS_ON');
  });

  it('renders a "no results" message when the graph is null', () => {
    render(<KnowledgeGraphPanel graph={null} />);
    expect(screen.getByText('No graph results found.')).toBeInTheDocument();
  });

  it('renders a "no results" message when the graph has no nodes', () => {
    const emptyGraph: KnowledgeGraphResult = { nodes: [], edges: [] };
    render(<KnowledgeGraphPanel graph={emptyGraph} />);
    expect(screen.getByText('No graph results found.')).toBeInTheDocument();
  });

  it('renders nodes without a type property gracefully', () => {
    const graphWithNoType: KnowledgeGraphResult = {
        nodes: [{ id: 'node3', label: 'Unknown Entity', properties: {} }],
        edges: []
    };
    render(<KnowledgeGraphPanel graph={graphWithNoType} />);
    expect(screen.getByText('Unknown Entity (Entity)')).toBeInTheDocument();
  });
}); 