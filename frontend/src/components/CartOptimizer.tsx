'use client';

import { useState, useEffect } from 'react';
import { api } from '../lib/api';

interface Aggregate {
  id: string;
  name: string;
  description: string;
  unit_of_measure: string;
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

interface OptimizationResult {
  selected_stores: StoreResult[];
  total_basket_cost: number;
  total_savings: number;
}

const UNIT_LABEL: Record<string, string> = {
  MASS: 'ק"ג',
  VOLUME: 'ל׳',
  UNITS: 'יח׳',
};

export default function CartOptimizer({ email }: { email: string }) {
  const [aggregates, setAggregates] = useState<Aggregate[]>([]);
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [maxStores, setMaxStores] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.aggregates.list(email).then(setAggregates).catch(console.error);
  }, [email]);

  const selectedAggregates = aggregates.filter(a => {
    const q = parseFloat(quantities[a.id] || '0');
    return q > 0;
  });

  const handleOptimize = async () => {
    if (selectedAggregates.length === 0) {
      setError('יש להזין כמות לפחות לקבוצה אחת');
      return;
    }
    setError('');
    setLoading(true);
    setResult(null);
    try {
      const list = await api.shoppingLists.create(email, {
        name: `סל ${new Date().toLocaleDateString('he-IL')}`,
        entries: selectedAggregates.map(a => ({
          aggregate_id: a.id,
          desired_amount: parseFloat(quantities[a.id]),
        })),
      });

      const opt = await api.optimization.optimize(email, {
        shopping_list_id: list.id,
        max_stores: maxStores,
      });
      setResult(opt);
    } catch (err: any) {
      setError(err.message || 'שגיאה בחישוב הסל');
    } finally {
      setLoading(false);
    }
  };

  if (aggregates.length === 0) {
    return (
      <section className="card">
        <h2>סל קניות אופטימלי</h2>
        <p style={{ marginTop: '1rem', color: 'var(--secondary)' }}>
          אין קבוצות מוצרים. עבור ללשונית "קבוצות מוצרים" ויצור קבוצות תחילה.
        </p>
      </section>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <section className="card">
        <h2 style={{ marginBottom: '1rem' }}>בחר כמויות לרשימת הקניות</h2>

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

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
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
            {selectedAggregates.length} קבוצות נבחרו
          </div>
          <button
            className="button"
            onClick={handleOptimize}
            disabled={loading || selectedAggregates.length === 0}
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
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
            <h2>תוצאות</h2>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--primary)' }}>
              סה"כ: ₪{Number(result.total_basket_cost).toFixed(2)}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {result.selected_stores.map((store, i) => (
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
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'right', color: 'var(--secondary)', fontWeight: 600 }}>קבוצה</th>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'right', color: 'var(--secondary)', fontWeight: 600 }}>מוצר זול ביותר</th>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'center', color: 'var(--secondary)', fontWeight: 600 }}>מחיר ליחידה</th>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'center', color: 'var(--secondary)', fontWeight: 600 }}>כמות</th>
                      <th style={{ padding: '0.5rem 1rem', textAlign: 'center', color: 'var(--secondary)', fontWeight: 600 }}>עלות</th>
                    </tr>
                  </thead>
                  <tbody>
                    {store.items.map(item => (
                      <tr key={item.aggregate_id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '0.55rem 1rem', fontWeight: 500 }}>{item.aggregate_name}</td>
                        <td style={{ padding: '0.55rem 1rem', color: 'var(--secondary)' }}>{item.item_name}</td>
                        <td style={{ padding: '0.55rem 1rem', textAlign: 'center' }}>₪{item.price_per_unit.toFixed(3)}</td>
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
