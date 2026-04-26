'use client';

import { useState, useEffect } from 'react';
import { api } from '../lib/api';

interface Aggregate {
  id: string;
  name: string;
  description: string;
  unit_of_measure: string;
}

interface Item {
  id: string;
  name: string;
  brand: string;
  item_code: string;
  unit_of_measure: string;
  quantity: number;
}

interface SpecificItem {
  item: Item;
  qty: number;
}

interface ShoppingListEntry {
  id: string;
  aggregate_id: string | null;
  item_id: string | null;
  desired_amount: number;
}

interface ShoppingList {
  id: string;
  name: string;
  created_at: string;
  entries: ShoppingListEntry[];
}

interface ItemResult {
  aggregate_id: string;
  aggregate_name: string;
  item_name: string;
  price_per_unit: number;
  desired_amount: number;
  cost: number;
}

interface StoreResult {
  store_id: string;
  store_name: string;
  chain_name: string;
  distance_km: number;
  items: ItemResult[];
  total_cost: number;
}

interface AlternativeStore {
  store_name: string;
  chain_name: string;
  total_cost: number;
}

interface OptimizationResult {
  selected_stores: StoreResult[];
  total_basket_cost: number;
  total_savings: number;
  alternatives: AlternativeStore[];
}

const UNIT_LABEL: Record<string, string> = {
  MASS: 'ק"ג',
  VOLUME: 'ל׳',
  UNITS: 'יח׳',
};

export default function CartOptimizer({ email }: { email: string }) {
  const [aggregates, setAggregates] = useState<Aggregate[]>([]);
  const [recentLists, setRecentLists] = useState<ShoppingList[]>([]);
  const [loadedListName, setLoadedListName] = useState('');
  const [showRecentLists, setShowRecentLists] = useState(false);
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [maxStores, setMaxStores] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [error, setError] = useState('');

  // Specific items
  const [specificItems, setSpecificItems] = useState<SpecificItem[]>([]);
  const [itemSearch, setItemSearch] = useState('');
  const [itemResults, setItemResults] = useState<Item[]>([]);
  const [itemSearchLoading, setItemSearchLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      api.aggregates.list(email),
      api.shoppingLists.list(email),
    ]).then(([aggs, lists]) => {
      setAggregates(aggs);
      const sorted = [...lists].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setRecentLists(sorted.slice(0, 5));
      if (sorted.length > 0) applyList(sorted[0], aggs);
    }).catch(console.error);
  }, [email]);

  const applyList = (list: ShoppingList, aggs?: Aggregate[]) => {
    const q: Record<string, string> = {};
    for (const entry of list.entries) {
      if (entry.aggregate_id) q[entry.aggregate_id] = String(entry.desired_amount);
    }
    setQuantities(q);
    setLoadedListName(list.name);
    setSpecificItems([]);
  };

  const selectedAggregates = aggregates.filter(a => {
    const q = parseFloat(quantities[a.id] || '0');
    return q > 0;
  });

  const handleItemSearch = async () => {
    if (itemSearch.length < 2) return;
    setItemSearchLoading(true);
    try {
      const data = await api.items.search(itemSearch);
      setItemResults(data);
    } catch (err) {
      console.error('Item search failed', err);
    } finally {
      setItemSearchLoading(false);
    }
  };

  const addSpecificItem = (item: Item) => {
    if (specificItems.find(s => s.item.id === item.id)) return;
    setSpecificItems(prev => [...prev, { item, qty: 1 }]);
  };

  const updateSpecificQty = (itemId: string, qty: number) => {
    setSpecificItems(prev => prev.map(s => s.item.id === itemId ? { ...s, qty: Math.max(1, Math.floor(qty)) } : s));
  };

  const removeSpecificItem = (itemId: string) => {
    setSpecificItems(prev => prev.filter(s => s.item.id !== itemId));
  };

  const handleOptimize = async () => {
    if (selectedAggregates.length === 0 && specificItems.length === 0) {
      setError('יש להזין כמות לפחות לפריט אחד');
      return;
    }
    setError('');
    setLoading(true);
    setResult(null);
    try {
      const entries = [
        ...selectedAggregates.map(a => ({
          aggregate_id: a.id,
          desired_amount: parseFloat(quantities[a.id]),
        })),
        ...specificItems.map(s => ({
          item_id: s.item.id,
          desired_amount: s.qty,
        })),
      ];

      const list = await api.shoppingLists.create(email, {
        name: `סל ${new Date().toLocaleDateString('he-IL')}`,
        entries,
      });

      const opt = await api.optimization.optimize(email, {
        shopping_list_id: list.id,
        max_stores: maxStores,
      });
      setResult(opt);

      api.shoppingLists.list(email).then(lists => {
        const sorted = [...lists].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
        setRecentLists(sorted.slice(0, 5));
      });
    } catch (err: any) {
      setError(err.message || 'שגיאה בחישוב הסל');
    } finally {
      setLoading(false);
    }
  };

  if (aggregates.length === 0 && specificItems.length === 0) {
    return (
      <section className="card">
        <h2>סל קניות אופטימלי</h2>
        <p style={{ marginTop: '1rem', color: 'var(--secondary)' }}>
          הוסף קבוצות מוצרים או חפש מוצרים ספציפיים למטה.
        </p>
      </section>
    );
  }

  const bestStoreName = result?.selected_stores[0]
    ? `${result.selected_stores[0].store_name}`
    : '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
          <h2>בחר כמויות לרשימת הקניות</h2>
          {recentLists.length > 0 && (
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setShowRecentLists(v => !v)}
                style={{
                  padding: '0.4rem 0.9rem', borderRadius: '6px', border: '1px solid var(--border)',
                  background: 'var(--card-bg)', color: 'var(--secondary)', fontSize: '0.85rem', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '0.4rem',
                }}
              >
                רשימות אחרונות ▾
              </button>
              {showRecentLists && (
                <div style={{
                  position: 'absolute', left: 0, top: '110%', zIndex: 10,
                  background: 'var(--card-bg)', border: '1px solid var(--border)',
                  borderRadius: '8px', minWidth: '220px', boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
                  overflow: 'hidden',
                }}>
                  {recentLists.map(list => (
                    <button
                      key={list.id}
                      onClick={() => { applyList(list); setShowRecentLists(false); }}
                      style={{
                        display: 'block', width: '100%', padding: '0.65rem 1rem',
                        textAlign: 'right', background: 'none', border: 'none',
                        cursor: 'pointer', borderBottom: '1px solid var(--border)',
                        color: 'var(--foreground)', fontSize: '0.88rem',
                      }}
                      onMouseOver={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.07)')}
                      onMouseOut={e => (e.currentTarget.style.background = 'none')}
                    >
                      <div style={{ fontWeight: 500 }}>{list.name}</div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--secondary)' }}>
                        {new Date(list.created_at).toLocaleDateString('he-IL')}
                        {' · '}{list.entries.length} פריטים
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {loadedListName && (
          <div style={{
            marginBottom: '0.75rem', padding: '0.4rem 0.8rem',
            background: 'rgba(99,102,241,0.08)', borderRadius: '6px',
            fontSize: '0.83rem', color: 'var(--secondary)', display: 'flex', alignItems: 'center', gap: '0.5rem',
          }}>
            <span>טעינה מ:</span>
            <span style={{ fontWeight: 500, color: 'var(--primary)' }}>{loadedListName}</span>
            <button
              onClick={() => { setQuantities({}); setLoadedListName(''); }}
              style={{ marginRight: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--secondary)', fontSize: '0.8rem' }}
            >
              ✕ נקה
            </button>
          </div>
        )}

        {aggregates.length > 0 && (
          <>
            <h3 style={{ marginBottom: '0.75rem', fontSize: '0.95rem', color: 'var(--secondary)' }}>קבוצות מוצרים</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
              {aggregates.map(agg => (
                <div key={agg.id} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '0.75rem 1rem', border: '1px solid var(--border)', borderRadius: '8px',
                  background: quantities[agg.id] && parseFloat(quantities[agg.id]) > 0
                    ? 'rgba(99,102,241,0.08)' : 'var(--card-bg)',
                }}>
                  <div>
                    <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{agg.name}</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--secondary)' }}>
                      {UNIT_LABEL[agg.unit_of_measure] ?? agg.unit_of_measure}
                    </div>
                  </div>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    placeholder="0"
                    value={quantities[agg.id] || ''}
                    onChange={e => setQuantities(q => ({ ...q, [agg.id]: e.target.value }))}
                    style={{
                      width: '72px', padding: '0.4rem 0.5rem', borderRadius: '6px',
                      border: '1px solid var(--border)', background: 'var(--card-bg)',
                      color: 'var(--foreground)', fontSize: '0.9rem', textAlign: 'center',
                    }}
                  />
                </div>
              ))}
            </div>
          </>
        )}

        {/* Specific items section */}
        <div style={{ borderTop: aggregates.length > 0 ? '1px solid var(--border)' : 'none', paddingTop: aggregates.length > 0 ? '1.5rem' : 0 }}>
          <h3 style={{ marginBottom: '0.75rem', fontSize: '0.95rem', color: 'var(--secondary)' }}>מוצרים ספציפיים</h3>

          {specificItems.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '0.6rem', marginBottom: '1rem' }}>
              {specificItems.map(({ item, qty }) => (
                <div key={item.id} style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  padding: '0.6rem 0.75rem', border: '1px solid var(--primary)', borderRadius: '8px',
                  background: 'rgba(99,102,241,0.06)',
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: '0.85rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--secondary)' }}>{item.brand}</div>
                  </div>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={qty}
                    onChange={e => updateSpecificQty(item.id, parseInt(e.target.value) || 1)}
                    style={{
                      width: '56px', padding: '0.3rem 0.4rem', borderRadius: '6px',
                      border: '1px solid var(--border)', background: 'var(--card-bg)',
                      color: 'var(--foreground)', fontSize: '0.9rem', textAlign: 'center',
                    }}
                  />
                  <span style={{ fontSize: '0.75rem', color: 'var(--secondary)', whiteSpace: 'nowrap' }}>יח׳</span>
                  <button
                    type="button"
                    onClick={() => removeSpecificItem(item.id)}
                    style={{ border: 'none', background: 'transparent', color: '#c00', cursor: 'pointer', fontSize: '1.1rem', padding: '0 2px', lineHeight: 1 }}
                  >×</button>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <input
              className="input"
              style={{ marginBottom: 0 }}
              placeholder="חפש מוצר להוספה..."
              value={itemSearch}
              onChange={e => setItemSearch(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleItemSearch()}
            />
            <button type="button" className="button" onClick={handleItemSearch} disabled={itemSearchLoading}>
              {itemSearchLoading ? 'מחפש...' : 'חפש'}
            </button>
          </div>

          {itemResults.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.5rem', maxHeight: '320px', overflowY: 'auto', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.75rem' }}>
              {itemResults.map(item => {
                const already = specificItems.some(s => s.item.id === item.id);
                return (
                  <div
                    key={item.id}
                    style={{
                      padding: '0.6rem 0.75rem', border: '1px solid var(--border)', borderRadius: '8px',
                      background: already ? 'rgba(99,102,241,0.08)' : 'var(--card-bg)',
                      display: 'flex', flexDirection: 'column', gap: '0.25rem',
                    }}
                  >
                    <div style={{ fontWeight: 500, fontSize: '0.82rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.name}>{item.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--secondary)' }}>{item.brand}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--secondary)' }}>
                      {item.quantity} {UNIT_LABEL[item.unit_of_measure] ?? item.unit_of_measure}
                    </div>
                    <button
                      type="button"
                      className="button-outline"
                      style={{ marginTop: '0.25rem', padding: '2px 8px', fontSize: '0.78rem', opacity: already ? 0.5 : 1 }}
                      onClick={() => addSpecificItem(item)}
                      disabled={already}
                    >
                      {already ? '✓ נוסף' : '+ הוסף'}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.9rem', color: 'var(--secondary)' }}>חנויות מקסימום:</label>
            <select
              value={maxStores}
              onChange={e => setMaxStores(Number(e.target.value))}
              style={{ padding: '0.4rem 0.5rem', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--card-bg)', color: 'var(--foreground)' }}
            >
              <option value={1}>1 חנות</option>
              <option value={2}>2 חנויות</option>
              <option value={3}>3 חנויות</option>
            </select>
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--secondary)' }}>
            {selectedAggregates.length + specificItems.length} פריטים נבחרו
          </div>
          <button
            className="button"
            onClick={handleOptimize}
            disabled={loading || (selectedAggregates.length === 0 && specificItems.length === 0)}
            style={{ marginRight: 'auto' }}
          >
            {loading ? 'מחשב...' : 'חשב סל אופטימלי'}
          </button>
        </div>

        {error && (
          <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'rgba(239,68,68,0.1)', borderRadius: '6px', color: '#ef4444', fontSize: '0.9rem' }}>
            {error}
          </div>
        )}
      </section>

      {result && (
        <section className="card">
          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--primary)' }}>
                ₪{Number(result.total_basket_cost).toFixed(2)}
              </span>
              <span style={{ fontSize: '1rem', fontWeight: 600 }}>ב{bestStoreName}</span>
            </div>

            {result.alternatives && result.alternatives.length > 0 && (
              <div style={{ marginTop: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap', fontSize: '0.9rem', color: 'var(--secondary)' }}>
                <span>במקום</span>
                {result.alternatives.map((alt, i) => {
                  const diff = alt.total_cost - result.total_basket_cost;
                  const pct = ((diff / result.total_basket_cost) * 100).toFixed(1);
                  return (
                    <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                      <span style={{ fontWeight: 600, color: 'var(--foreground)' }}>₪{Number(alt.total_cost).toFixed(2)}</span>
                      <span style={{
                        fontSize: '0.78rem', background: 'rgba(239,68,68,0.1)',
                        color: '#ef4444', borderRadius: '4px', padding: '0.1rem 0.35rem', fontWeight: 600,
                      }}>+{pct}%</span>
                      <span>ב{alt.store_name}</span>
                      {i < result.alternatives.length - 1 && <span style={{ color: 'var(--border)' }}>·</span>}
                    </span>
                  );
                })}
              </div>
            )}

            {result.total_savings > 0 && (
              <div style={{ marginTop: '0.35rem', fontSize: '0.88rem', color: '#22c55e', fontWeight: 500 }}>
                חיסכון של ₪{Number(result.total_savings).toFixed(2)} לעומת האפשרות הזולה הבאה
              </div>
            )}
          </div>

          <h2 style={{ marginBottom: '1rem', fontSize: '1rem', color: 'var(--secondary)', fontWeight: 600 }}>פירוט לפי חנות</h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {result.selected_stores.map((store) => (
              <div key={store.store_id} style={{ border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.75rem 1rem', background: 'rgba(99,102,241,0.08)',
                }}>
                  <div>
                    <span style={{ fontWeight: 600 }}>{store.store_name}</span>
                    <span style={{
                      marginRight: '0.75rem', fontSize: '0.8rem', background: 'rgba(99,102,241,0.15)',
                      color: 'var(--primary)', borderRadius: '4px', padding: '0.2rem 0.5rem',
                    }}>{store.chain_name}</span>
                  </div>
                  <span style={{ fontWeight: 600, color: 'var(--primary)' }}>₪{Number(store.total_cost).toFixed(2)}</span>
                </div>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--card-bg)' }}>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'right', color: 'var(--secondary)', fontWeight: 600 }}>פריט</th>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'right', color: 'var(--secondary)', fontWeight: 600 }}>מוצר זול ביותר</th>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'center', color: 'var(--secondary)', fontWeight: 600 }}>מחיר ליח׳</th>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'center', color: 'var(--secondary)', fontWeight: 600 }}>כמות</th>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'center', color: 'var(--secondary)', fontWeight: 600 }}>עלות</th>
                    </tr>
                  </thead>
                  <tbody>
                    {store.items.map(item => (
                      <tr key={item.aggregate_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '0.55rem 1rem', fontWeight: 500 }}>{item.aggregate_name}</td>
                        <td style={{ padding: '0.55rem 1rem', color: 'var(--secondary)' }}>{item.item_name}</td>
                        <td style={{ padding: '0.55rem 1rem', textAlign: 'center' }}>₪{item.price_per_unit.toFixed(2)}</td>
                        <td style={{ padding: '0.55rem 1rem', textAlign: 'center' }}>{item.desired_amount}</td>
                        <td style={{ padding: '0.55rem 1rem', textAlign: 'center', fontWeight: 600, color: 'var(--primary)' }}>₪{item.cost.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
