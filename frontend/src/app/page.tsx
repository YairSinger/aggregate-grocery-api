'use client';

import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import Auth from '../components/Auth';
import AggregatorManager from '../components/AggregatorManager';

export default function Home() {
  const [email, setEmail] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [aggregatesCount, setAggregatesCount] = useState(0);

  const handleLogin = (userEmail: string) => {
    localStorage.setItem('user_email', userEmail);
    setEmail(userEmail);
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('user_email');
    setIsLoggedIn(false);
    setEmail('');
  };

  const refreshData = async () => {
    if (!email) return;
    try {
      const data = await api.aggregates.list(email);
      setAggregatesCount(data.length);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    const savedEmail = localStorage.getItem('user_email');
    if (savedEmail) {
      setEmail(savedEmail);
      setIsLoggedIn(true);
    }
  }, []);

  useEffect(() => {
    if (isLoggedIn) {
      refreshData();
    }
  }, [isLoggedIn, email]);

  if (!isLoggedIn) {
    return <Auth onLogin={handleLogin} />;
  }

  return (
    <main className="container">
      <div style={{ display: 'flex', gap: '2rem', flexDirection: 'column' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>שלום, {email}</h1>
            <p style={{ color: 'var(--secondary)' }}>נהל את קבוצות המוצרים שלך והשווה מחירים</p>
          </div>
          <button className="button" style={{ background: 'var(--secondary)' }} onClick={handleLogout}>התנתק</button>
        </header>

        <AggregatorManager email={email} onUpdate={refreshData} />

        <section className="card">
          <h2>תכנון סל קניות</h2>
          <p style={{ marginTop: '1rem', color: 'var(--secondary)' }}>
            יש לך {aggregatesCount} קבוצות מוצרים מוגדרות. 
            בשלב הבא תוכל לבחור קבוצות ולחשב את הסל האופטימלי.
          </p>
          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
            <button className="button" disabled={aggregatesCount === 0}>עבור לתכנון רשימת קניות</button>
            <button className="button-outline" onClick={refreshData}>רענן נתונים</button>
          </div>
        </section>
      </div>
    </main>
  );
}
