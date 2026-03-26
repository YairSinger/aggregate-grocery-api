'use client';

import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import Auth from '../components/Auth';

export default function Home() {
  const [email, setEmail] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [aggregates, setAggregates] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleLogin = (userEmail: string) => {
    localStorage.setItem('user_email', userEmail);
    setEmail(userEmail);
    setIsLoggedIn(true);
    loadUserData(userEmail);
  };


  const loadUserData = async (userEmail: string) => {
    try {
      const data = await api.aggregates.list(userEmail);
      setAggregates(data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSearch = async () => {
    if (searchQuery.length < 2) return;
    setLoading(true);
    try {
      const results = await api.items.search(searchQuery);
      setSearchResults(results);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const savedEmail = localStorage.getItem('user_email');
    if (savedEmail) {
      setEmail(savedEmail);
      setIsLoggedIn(true);
      loadUserData(savedEmail);
    }
  }, []);

  if (!isLoggedIn) {
    return <Auth onLogin={handleLogin} />;
  }

  return (
    <main className="container">
      <div style={{ display: 'flex', gap: '2rem', flexDirection: 'column' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1>שלום, {email}</h1>
          <button className="button" style={{ background: 'var(--secondary)' }} onClick={() => {
            localStorage.removeItem('user_email');
            setIsLoggedIn(false);
          }}>התנתק</button>
        </header>

        <section className="grid">
          <div className="card">
            <h2>חיפוש מוצרים</h2>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
              <input 
                className="input"
                style={{ marginBottom: 0 }}
                placeholder="חפש מוצר (למשל: חלב)" 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button className="button" onClick={handleSearch}>חפש</button>
            </div>
            
            <div style={{ marginTop: '1rem', maxHeight: '300px', overflowY: 'auto' }}>
              {searchResults.map(item => (
                <div key={item.id} style={{ padding: '0.5rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between' }}>
                  <span>{item.name} ({item.brand})</span>
                  <button style={{ color: 'var(--primary)', border: 'none', background: 'none', cursor: 'pointer' }}>הוסף לקבוצה</button>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h2>הקבוצות שלי (Aggregates)</h2>
            <div style={{ marginTop: '1rem' }}>
              {aggregates.length === 0 ? (
                 <p style={{ color: 'var(--secondary)' }}>אין קבוצות עדיין. חפש מוצרים והוסף אותם לקבוצה חדשה.</p>
              ) : (
                aggregates.map(agg => (
                  <div key={agg.id} className="card" style={{ marginBottom: '0.5rem', padding: '1rem' }}>
                    <strong>{agg.name}</strong> ({agg.unit_of_measure})
                    <p style={{ fontSize: '0.8rem', color: 'var(--secondary)' }}>{agg.items.length} מוצרים בקבוצה</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        <section className="card">
          <h2>תכנון סל קניות</h2>
          <p style={{ marginTop: '1rem', color: 'var(--secondary)' }}>בחר קבוצות מהרשימה לעיל והוסף אותן לסל לקבלת המחיר הזול ביותר.</p>
          <button className="button" style={{ marginTop: '1rem' }} disabled={aggregates.length === 0}>חשב סל אופטימלי</button>
        </section>
      </div>
    </main>
  );
}
