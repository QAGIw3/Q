import React from 'react';
import './UITable.css';

interface UITableProps {
    headers: string[];
    rows: Record<string, any>[];
}

export const UITableComponent: React.FC<UITableProps> = ({ headers, rows }) => {
    return (
        <div className="ui-table-container">
            <table className="ui-table">
                <thead>
                    <tr>
                        {headers.map((header, index) => (
                            <th key={index}>{header}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                            {headers.map((header, colIndex) => (
                                <td key={colIndex}>{JSON.stringify(row[header])}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}; 