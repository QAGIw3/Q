// WebAppQ/app/src/pages/RegisterPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { register } from '../services/authAPI';

export const RegisterPage: React.FC = () => {
    const [username, setUsername] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const navigate = useNavigate();

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setSuccess(null);

        try {
            await register({ username, email, password, first_name: firstName, last_name: lastName });
            setSuccess("Registration successful! You can now log in.");
            // Optionally, redirect to login page after a delay
            setTimeout(() => navigate('/'), 2000);
        } catch (err: any) {
            setError(err.message || 'Failed to register.');
        }
    };

    return (
        <div style={{ padding: '50px', maxWidth: '400px', margin: 'auto' }}>
            <h2>Register</h2>
            <form onSubmit={handleRegister}>
                {/* Add form fields for username, email, password, etc. */}
                {/* ... similar to LoginPage ... */}
                 <div style={{ marginBottom: '15px' }}>
                    <label>Username</label>
                    <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required style={{ width: '100%', padding: '8px' }}/>
                </div>
                <div style={{ marginBottom: '15px' }}>
                    <label>Email</label>
                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ width: '100%', padding: '8px' }}/>
                </div>
                <div style={{ marginBottom: '15px' }}>
                    <label>Password</label>
                    <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ width: '100%', padding: '8px' }}/>
                </div>
                 <div style={{ marginBottom: '15px' }}>
                    <label>First Name</label>
                    <input type="text" value={firstName} onChange={(e) => setFirstName(e.target.value)} style={{ width: '100%', padding: '8px' }}/>
                </div>
                <div style={{ marginBottom: '15px' }}>
                    <label>Last Name</label>
                    <input type="text" value={lastName} onChange={(e) => setLastName(e.target.value)} style={{ width: '100%', padding: '8px' }}/>
                </div>
                {error && <p style={{ color: 'red' }}>{error}</p>}
                {success && <p style={{ color: 'green' }}>{success}</p>}
                <button type="submit" style={{ width: '100%', padding: '10px' }}>
                    Register
                </button>
            </form>
        </div>
    );
}; 