'use client';

import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import Auth from '../components/Auth';
import AggregatorManager from '../components/AggregatorManager';
import ItemsTable from '../components/ItemsTable';

type Tab = 'aggregates' | 'items' | 'cart';

export default function Home() {
  const [email, setEmail] = useState('');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [aggregatesCount, setAggregatesCount] = useState(0);
  const [tab, setTab] = useState<Tab>('items');

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
    if (savedEmail) { setEmail(savedEmail); setIsLoggedIn(true); }
  }, []);

  useEffect(() => { if (isLoggedIn) refreshData(); }, [isLoggedIn, email]);

  if (!isLoggedIn) return <Auth onLogin={handleLogin} />;

  const tabs: { key: Tab; label: string }[] = [
    { key: 'items',      label: 'מוצרים ומחירים' },
    { key: 'aggregates', label: 'קבוצות מוצרים' },
    { key: 'cart',       label: 'סל קניות אופטימלי' },
  ];

  return (
    <main className="container">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1>שלום, {email}</h1>
          <p style={{ color: 'var(--secondary)' }}>השוואת מחירי מכולת</p>
        </div>
        <button className="button" style={{ background: 'var(--secondary)' }} onClick={handleLogout}>התנתק</button>
      </header>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '2px solid var(--border)', paddingBottom: '0' }}>
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: '0.6rem 1.2rem',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              fontWeight: tab === t.key ? 700 : 400,
              color: tab === t.key ? 'var(--primary)' : 'var(--secondary)',
              borderBottom: tab === t.key ? '2px solid var(--primary)' : '2px solid transparent',
              marginBottom: '-2px',
              fontSize: '0.95rem',
              transition: 'color 0.15s',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'items' && <ItemsTable />}

      {tab === 'aggregates' && <AggregatorManager email={email} onUpdate={refreshData} />}

      {tab === 'cart' && (
        <section className="card">
          <h2>סל קניות אופטימלי</h2>
          <p style={{ marginTop: '1rem', color: 'var(--secondary)' }}>
            יש לך {aggregatesCount} קבוצות מוצרים מוגדרות.
            בשלב הבא תוכל לבחור קבוצות ולחשב את הסל האופטימלי.
          </p>
          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
            <button className="button" disabled={aggregatesCount === 0} onClick={() => setTab('aggregates')}>
              {aggregatesCount === 0 ? 'הוסף קבוצות מוצרים תחילה' : 'עבור לתכנון רשימת קניות'}
            </button>
            <button className="button-outline" onClick={refreshData}>רענן נתונים</button>
          </div>
        </section>
      )}
    </main>
  );
}
