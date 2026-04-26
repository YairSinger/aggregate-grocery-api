'use client';

import { useState, useEffect } from 'react';
import { api } from '../lib/api';

interface Item {
  id: string;
  name: string;
  brand: string;
  item_code: string;
}

interface Aggregate {
  id: string;
  name: string;
  description: string;
  unit_of_measure: string;
  items: { item: Item }[];
}

export default function AggregatorManager({ email, onUpdate }: { email: string, onUpdate: () => void }) {
  const [aggregates, setAggregates] = useState<Aggregate[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Item[]>([]);
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set());
  const [editingAggregate, setEditingAggregate] = useState<Partial<Aggregate> | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchAggregates = async () => {
    try {
      const data = await api.aggregates.list(email);
      setAggregates(data);
    } catch (err) {
      console.error('Failed to fetch aggregates', err);
    }
  };

  useEffect(() => {
    fetchAggregates();
  }, [email]);

  const handleSearch = async () => {
    if (searchQuery.length < 2) return;
    setLoading(true);
    try {
      const data = await api.items.search(searchQuery);
      setSearchResults(data);
    } catch (err) {
      console.error('Search failed', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleItemSelection = (id: string) => {
    const next = new Set(selectedItemIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedItemIds(next);
  };

  const selectAll = () => {
    setSelectedItemIds(new Set(searchResults.map(i => i.id)));
  };

  const deselectAll = () => {
    setSelectedItemIds(new Set());
  };

  const handleSaveAggregate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAggregate?.name || !editingAggregate?.unit_of_measure) return;

    try {
      const payload = {
        name: editingAggregate.name,
        description: editingAggregate.description,
        unit_of_measure: editingAggregate.unit_of_measure,
        item_ids: Array.from(selectedItemIds),
      };

      if (editingAggregate.id) {
        await api.aggregates.update(email, editingAggregate.id, payload);
      } else {
        await api.aggregates.create(email, payload);
      }

      setEditingAggregate(null);
      setSelectedItemIds(new Set());
      setSearchResults([]);
      setSearchQuery('');
      fetchAggregates();
      onUpdate();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const removeItemFromAggregate = async (agg: Aggregate, itemId: string) => {
    try {
      await api.aggregates.update(email, agg.id, {
        name: agg.name,
        description: agg.description,
        unit_of_measure: agg.unit_of_measure,
        item_ids: agg.items.map(i => i.item.id).filter(id => id !== itemId),
      });
      fetchAggregates();
      onUpdate();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const deleteAggregate = async (agg: Aggregate) => {
    if (!window.confirm(`למחוק את הקבוצה "${agg.name}"?`)) return;
    try {
      await api.aggregates.delete(email, agg.id);
      fetchAggregates();
      onUpdate();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const startEditing = (agg: Aggregate) => {
    setEditingAggregate(agg);
    setSelectedItemIds(new Set(agg.items.map(i => i.item.id)));
    // Optionally load current items into search results or just show them
  };

  const startNew = () => {
    setEditingAggregate({
      name: '',
      description: '',
      unit_of_measure: 'MASS',
    });
    setSelectedItemIds(new Set());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2>הקבוצות שלי</h2>
          <button className="button" onClick={startNew}>+ קבוצה חדשה</button>
        </div>
        
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))' }}>
          {aggregates.map(agg => (
            <div key={agg.id} className="card" style={{ border: '1px solid var(--border)' }}>
              <h3>{agg.name}</h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--secondary)', minHeight: '3em' }}>{agg.description || 'אין תיאור'}</p>
              {agg.items.length > 0 && (
                <ul style={{ listStyle: 'none', padding: 0, margin: '0.5rem 0', fontSize: '0.85rem' }}>
                  {agg.items.slice(0, 3).map(({ item }) => (
                    <li key={item.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', padding: '2px 0' }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
                      <button
                        type="button"
                        onClick={() => removeItemFromAggregate(agg, item.id)}
                        title="הסר מוצר"
                        style={{ border: 'none', background: 'transparent', color: 'var(--secondary)', cursor: 'pointer', fontSize: '1rem', lineHeight: 1, padding: '0 4px' }}
                      >×</button>
                    </li>
                  ))}
                  {agg.items.length > 3 && (
                    <li style={{ color: 'var(--secondary)', fontStyle: 'italic', padding: '2px 0' }}>
                      + {agg.items.length - 3} נוספים
                    </li>
                  )}
                </ul>
              )}
              <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                <span className="badge">{agg.unit_of_measure}</span>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="button-outline" onClick={() => startEditing(agg)}>ערוך</button>
                  <button className="button-outline" style={{ color: '#c00', borderColor: '#c00' }} onClick={() => deleteAggregate(agg)}>מחק</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {editingAggregate && (
        <section className="card" style={{ border: '2px solid var(--primary)' }}>
          <h2>{editingAggregate.id ? 'עריכת קבוצה' : 'יצירת קבוצה חדשה'}</h2>
          <form onSubmit={handleSaveAggregate} style={{ marginTop: '1rem' }}>
            <div className="grid">
              <div>
                <label>שם הקבוצה</label>
                <input 
                  className="input" 
                  required
                  value={editingAggregate.name} 
                  onChange={e => setEditingAggregate({...editingAggregate, name: e.target.value})}
                />
              </div>
              <div>
                <label>יחידת מידה</label>
                <select 
                  className="input"
                  value={editingAggregate.unit_of_measure}
                  onChange={e => setEditingAggregate({...editingAggregate, unit_of_measure: e.target.value})}
                >
                  <option value="MASS">משקל (ק"ג)</option>
                  <option value="VOLUME">נפח (ליטר)</option>
                  <option value="UNITS">יחידות</option>
                </select>
              </div>
            </div>
            
            <div style={{ marginTop: '1rem' }}>
              <label>תיאור</label>
              <textarea 
                className="input"
                style={{ height: '80px' }}
                value={editingAggregate.description}
                onChange={e => setEditingAggregate({...editingAggregate, description: e.target.value})}
                placeholder="הוסף תיאור לשימוש עתידי..."
              />
            </div>

            {editingAggregate.items && editingAggregate.items.length > 0 && (
              <div style={{ marginTop: '2rem', padding: '1rem', background: '#f9f9f9', borderRadius: '8px' }}>
                <h3>מוצרים בקבוצה ({selectedItemIds.size})</h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: '0.75rem 0 0', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {editingAggregate.items.map(({ item }) => {
                    const active = selectedItemIds.has(item.id);
                    return (
                      <li key={item.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '4px 8px', borderRadius: '4px', background: active ? '#fff' : '#fde', border: '1px solid #eee', opacity: active ? 1 : 0.5, minWidth: 0 }}>
                        <span style={{ flex: 1, fontSize: '0.85rem', textDecoration: active ? 'none' : 'line-through', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.name} <small style={{ color: 'var(--secondary)' }}>({item.brand})</small>
                        </span>
                        {active ? (
                          <button
                            type="button"
                            onClick={() => { const n = new Set(selectedItemIds); n.delete(item.id); setSelectedItemIds(n); }}
                            title="הסר מוצר"
                            style={{ border: 'none', background: 'transparent', color: '#c00', cursor: 'pointer', fontSize: '1.1rem', lineHeight: 1, padding: '0 4px' }}
                          >×</button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => { const n = new Set(selectedItemIds); n.add(item.id); setSelectedItemIds(n); }}
                            title="החזר מוצר"
                            style={{ border: 'none', background: 'transparent', color: 'green', cursor: 'pointer', fontSize: '0.8rem', padding: '0 4px' }}
                          >↩</button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            <div style={{ marginTop: '2rem', padding: '1rem', background: '#f9f9f9', borderRadius: '8px' }}>
              <h3>חיפוש והוספת מוצרים לקבוצה</h3>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                <input 
                  className="input"
                  style={{ marginBottom: 0 }}
                  placeholder="חפש מוצר להוספה..." 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <button type="button" className="button" onClick={handleSearch} disabled={loading}>
                  {loading ? 'מחפש...' : 'חפש'}
                </button>
              </div>

              {searchResults.length > 0 && (
                <div style={{ marginTop: '1rem' }}>
                  <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
                    <button type="button" className="button-outline" style={{ padding: '2px 8px', fontSize: '0.8rem' }} onClick={selectAll}>בחר הכל</button>
                    <button type="button" className="button-outline" style={{ padding: '2px 8px', fontSize: '0.8rem' }} onClick={deselectAll}>בטל בחירה</button>
                  </div>
                  <div style={{ maxHeight: '250px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '4px' }}>
                    {searchResults.map(item => (
                      <label key={item.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem', borderBottom: '1px solid #eee', cursor: 'pointer' }}>
                        <input 
                          type="checkbox" 
                          checked={selectedItemIds.has(item.id)}
                          onChange={() => toggleItemSelection(item.id)}
                        />
                        <span>{item.name} <small style={{ color: 'var(--secondary)' }}>({item.brand})</small></span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
              
              <div style={{ marginTop: '1rem', fontSize: '0.9rem' }}>
                <strong>נבחרו {selectedItemIds.size} מוצרים</strong>
              </div>
            </div>

            <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button type="button" className="button" style={{ background: 'var(--secondary)' }} onClick={() => setEditingAggregate(null)}>ביטול</button>
              <button type="submit" className="button">שמור קבוצה</button>
            </div>
          </form>
        </section>
      )}
    </div>
  );
}
