import React, { useState } from 'react';

export const UIFormComponent: React.FC<{ schema: any, onSubmit: (data: any) => void }> = ({ schema, onSubmit }) => {
    const [formData, setFormData] = useState<any>({});

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit(formData);
    };

    return (
        <form onSubmit={handleSubmit}>
            {Object.keys(schema.properties).map(key => (
                <div key={key}>
                    <label>{schema.properties[key].title}</label>
                    <input
                        type={schema.properties[key].type}
                        name={key}
                        onChange={handleChange}
                        required={schema.required.includes(key)}
                    />
                </div>
            ))}
            <button type="submit">Submit</button>
        </form>
    );
}; 