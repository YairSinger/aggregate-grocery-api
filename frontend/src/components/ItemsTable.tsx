'use client';

import { useState, useEffect, useCallback } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8030/api/v1';

interface ItemRow {
  id: string;
  name: string;
  brand: string | null;
  category: string | null;
  unit_of_measure: string;
  quantity: number;
  min_price: number | null;
  max_price: number | null;
  price_per_unit: number | null;
  best_chain: string | null;
  store_count: number;
}

type SortKey = 'name' | 'brand' | 'category' | 'min_price' | 'price_per_unit' | 'store_count';

const UNIT_LABEL: Record<string, string> = {
  MASS: 'ק"ג',
  VOLUME: 'ל׳',
  UNITS: 'יח׳',
};

const PAGE_SIZE = 100;

export default function ItemsTable() {
  const [items, setItems] = useState<ItemRow[]>([]);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sortBy, setSortBy] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(search);
      setOffset(0);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        sort_by: sortBy,
        sort_dir: sortDir,
        limit: String(PAGE_SIZE),
        offset: String(offset),
      });
      if (debouncedSearch) params.set('q', debouncedSearch);
      const res = await fetch(`${API}/items/?${params}`);
      const data: ItemRow[] = await res.json();
      setItems(data);
      setHasMore(data.length === PAGE_SIZE);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortDir, offset, debouncedSearch]);

  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleSort = (col: SortKey) => {
    if (col === sortBy) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('asc');
    }
    setOffset(0);
  };

  const arrow = (col: SortKey) => sortBy === col ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';

  const fmt = (n: number | null, digits = 2) =>
    n == null ? '—' : `₪${n.toFixed(digits)}`;

  const fmtUnit = (row: ItemRow) => {
    if (row.price_per_unit == null) return '—';
    const unit = UNIT_LABEL[row.unit_of_measure] ?? row.unit_of_measure;
    return `₪${row.price_per_unit.toFixed(2)} / ${unit}`;
  };

  return (
    <section className="card" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h2 style={{ margin: 0 }}>כל המוצרים</h2>
        <input
          type="search"
          placeholder="חיפוש לפי שם, מותג, קטגוריה..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            padding: '0.5rem 0.75rem',
            borderRadius: '6px',
            border: '1px solid var(--border)',
            fontSize: '0.9rem',
            width: '280px',
            background: 'var(--card-bg)',
            color: 'var(--foreground)',
          }}
        />
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--border)', background: 'var(--card-bg)' }}>
              {([
                ['name',        'מוצר'],
                ['brand',       'מותג'],
                ['category',    'קטגוריה'],
                [null,          'כמות'],
                ['min_price',   'מחיר מינימום'],
                ['price_per_unit', 'מחיר מנורמל'],
                [null,          'רשת זולה'],
                ['store_count', 'חנויות'],
              ] as [SortKey | null, string][]).map(([col, label]) => (
                <th
                  key={label}
                  onClick={col ? () => handleSort(col) : undefined}
                  style={{
                    padding: '0.6rem 0.8rem',
                    textAlign: 'right',
                    whiteSpace: 'nowrap',
                    cursor: col ? 'pointer' : 'default',
                    userSelect: 'none',
                    color: col && sortBy === col ? 'var(--primary)' : 'var(--secondary)',
                    fontWeight: 600,
                  }}
                >
                  {label}{col ? arrow(col) : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && items.length === 0 ? (
              <tr><td colSpan={8} style={{ textAlign: 'center', padding: '2rem', color: 'var(--secondary)' }}>טוען...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={8} style={{ textAlign: 'center', padding: '2rem', color: 'var(--secondary)' }}>לא נמצאו מוצרים</td></tr>
            ) : items.map((item, i) => (
              <tr
                key={item.id}
                style={{
                  borderBottom: '1px solid var(--border)',
                  background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
                }}
              >
                <td style={{ padding: '0.55rem 0.8rem', fontWeight: 500 }}>{item.name}</td>
                <td style={{ padding: '0.55rem 0.8rem', color: 'var(--secondary)' }}>{item.brand ?? '—'}</td>
                <td style={{ padding: '0.55rem 0.8rem', color: 'var(--secondary)' }}>{item.category ?? '—'}</td>
                <td style={{ padding: '0.55rem 0.8rem', textAlign: 'center' }}>
                  {item.quantity} {UNIT_LABEL[item.unit_of_measure] ?? item.unit_of_measure}
                </td>
                <td style={{ padding: '0.55rem 0.8rem', textAlign: 'center', fontWeight: 600, color: 'var(--primary)' }}>
                  {fmt(item.min_price)}
                  {item.max_price != null && item.max_price !== item.min_price && (
                    <span style={{ color: 'var(--secondary)', fontWeight: 400 }}> – {fmt(item.max_price)}</span>
                  )}
                </td>
                <td style={{ padding: '0.55rem 0.8rem', textAlign: 'center' }}>{fmtUnit(item)}</td>
                <td style={{ padding: '0.55rem 0.8rem', textAlign: 'center' }}>
                  {item.best_chain ? (
                    <span style={{
                      background: 'rgba(99,102,241,0.15)',
                      color: 'var(--primary)',
                      borderRadius: '4px',
                      padding: '0.2rem 0.5rem',
                      fontSize: '0.8rem',
                    }}>{item.best_chain}</span>
                  ) : '—'}
                </td>
                <td style={{ padding: '0.55rem 0.8rem', textAlign: 'center', color: 'var(--secondary)' }}>{item.store_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}>
        <span style={{ color: 'var(--secondary)', fontSize: '0.85rem' }}>
          {loading ? 'טוען...' : `מציג ${items.length} מוצרים`}
        </span>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="button-outline"
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0 || loading}
            style={{ padding: '0.4rem 0.9rem', fontSize: '0.85rem' }}
          >
            ← הקודם
          </button>
          <button
            className="button-outline"
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={!hasMore || loading}
            style={{ padding: '0.4rem 0.9rem', fontSize: '0.85rem' }}
          >
            הבא →
          </button>
        </div>
      </div>
    </section>
  );
}
