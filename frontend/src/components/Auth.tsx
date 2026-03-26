'use client';

import { useState } from 'react';
import { api } from '../lib/api';

interface AuthProps {
  onLogin: (email: string) => void;
}

export default function Auth({ onLogin }: AuthProps) {
  const [email, setEmail] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      if (isRegister) {
        await api.auth.register(email);
        setMessage('נרשמת בהצלחה! כעת ניתן להתחבר.');
        setIsRegister(false);
      } else {
        await api.auth.me(email);
        onLogin(email);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="card auth-card">
        <h1 style={{ marginBottom: '0.5rem' }}>{isRegister ? 'הרשמה למערכת' : 'התחברות'}</h1>
        <p style={{ color: 'var(--secondary)', marginBottom: '1.5rem' }}>
          {isRegister ? 'הכנס אימייל כדי להצטרף' : 'הכנס אימייל כדי להמשיך'}
        </p>

        {message && <p style={{ color: 'var(--success)', marginBottom: '1rem', fontWeight: '500' }}>{message}</p>}
        {error && <p style={{ color: 'var(--error)', marginBottom: '1rem', fontWeight: '500' }}>{error}</p>}

        <form onSubmit={handleSubmit}>
          <input
            className="input"
            type="email"
            placeholder="אימייל"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <button className="button" style={{ width: '100%' }} type="submit" disabled={loading}>
            {loading ? 'מעבד...' : (isRegister ? 'הרשם עכשיו' : 'התחבר')}
          </button>
        </form>

        <div className="auth-toggle">
          {isRegister ? (
            <p>
              כבר יש לך חשבון? <button onClick={() => setIsRegister(false)}>התחבר כאן</button>
            </p>
          ) : (
            <p>
              אין לך חשבון? <button onClick={() => setIsRegister(true)}>צור חשבון חדש</button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
