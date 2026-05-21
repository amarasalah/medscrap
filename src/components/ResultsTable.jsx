'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { useEffect, useState, useMemo } from 'react';
import { FiChevronUp, FiChevronDown, FiChevronLeft, FiChevronRight, FiPhone, FiMapPin } from 'react-icons/fi';
import { RiStethoscopeLine } from 'react-icons/ri';
import { primaryAddress, primaryPhone } from '@/lib/doctor';

export default function ResultsTable({ data, onSelect }) {
  const { t } = useLanguage();
  const [sortKey, setSortKey] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(25);

  function sortValue(d, key) {
    if (key === 'city' || key === 'department') return primaryAddress(d)?.[key] || '';
    if (key === 'phone') return primaryPhone(d)?.formatted || '';
    return d[key] || '';
  }

  const sorted = useMemo(() => {
    const arr = [...data];
    arr.sort((a, b) => {
      const aVal = sortValue(a, sortKey).toString().toLowerCase();
      const bVal = sortValue(b, sortKey).toString().toLowerCase();
      if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return arr;
  }, [data, sortKey, sortDir]);

  const totalPages = Math.ceil(sorted.length / perPage);
  const paginated = sorted.slice((page - 1) * perPage, page * perPage);

  useEffect(() => { setPage(1); }, [data.length]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span className="sort-icon inactive">⇅</span>;
    return sortDir === 'asc'
      ? <FiChevronUp className="sort-icon active" />
      : <FiChevronDown className="sort-icon active" />;
  };

  const columns = [
    { key: 'name', label: t('name'), width: '22%' },
    { key: 'specialty', label: t('specialty'), width: '18%' },
    { key: 'city', label: t('city'), width: '14%' },
    { key: 'department', label: t('department'), width: '14%' },
    { key: 'phone', label: t('phone'), width: '12%' },
    { key: 'convention', label: t('convention'), width: '14%' },
  ];

  const getPageNumbers = () => {
    const pages = [];
    const maxVisible = 5;
    if (totalPages <= maxVisible + 2) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      let start = Math.max(2, page - 1);
      let end = Math.min(totalPages - 1, page + 1);
      if (page <= 3) { start = 2; end = maxVisible; }
      if (page >= totalPages - 2) { start = totalPages - maxVisible + 1; end = totalPages - 1; }
      if (start > 2) pages.push('...');
      for (let i = start; i <= end; i++) pages.push(i);
      if (end < totalPages - 1) pages.push('...');
      pages.push(totalPages);
    }
    return pages;
  };

  if (data.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          <RiStethoscopeLine />
        </div>
        <h3>{t('noResults')}</h3>
        <p>{t('noResultsSub')}</p>
      </div>
    );
  }

  return (
    <div className="results-container">
      <div className="table-wrap">
        <table className="results-table" id="results-table">
          <thead>
            <tr>
              <th className="th-num">#</th>
              {columns.map(col => (
                <th
                  key={col.key}
                  style={{ width: col.width }}
                  onClick={() => handleSort(col.key)}
                  className="sortable-th"
                >
                  <span>{col.label}</span>
                  <SortIcon col={col.key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginated.map((doc, i) => {
              const addr = primaryAddress(doc);
              const phone = primaryPhone(doc);
              const extraAddr = (doc.addresses?.length || 0) - 1;
              const extraPhone = (doc.phones?.length || 0) - 1;
              return (
                <tr
                  key={doc.id}
                  className="table-row"
                  onClick={() => onSelect(doc)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && onSelect(doc)}
                >
                  <td className="td-num">{(page - 1) * perPage + i + 1}</td>
                  <td className="td-name">
                    <span className={`type-dot ${doc.type === 'professionnel_de_sante' ? 'dot-pro' : 'dot-inst'}`} />
                    {doc.name}
                  </td>
                  <td className="td-specialty">{doc.specialty || '—'}</td>
                  <td className="td-city">
                    {addr?.city ? (
                      <>
                        <FiMapPin className="cell-icon" /> {addr.city}
                        {extraAddr > 0 && <span className="multi-badge"> +{extraAddr}</span>}
                      </>
                    ) : '—'}
                  </td>
                  <td className="td-dept">{addr?.department || '—'}</td>
                  <td className="td-phone">
                    {phone ? (
                      <>
                        <FiPhone className="cell-icon" /> {phone.formatted}
                        {extraPhone > 0 && <span className="multi-badge"> +{extraPhone}</span>}
                      </>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="td-convention">
                    {doc.convention ? (
                      <span className={`convention-badge ${doc.convention.includes('1') ? 'conv-1' : 'conv-2'}`}>
                        {doc.convention.replace('Conventionné ', '')}
                      </span>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <div className="pagination-info">
          {t('showing')} {((page - 1) * perPage + 1).toLocaleString()}–{Math.min(page * perPage, sorted.length).toLocaleString()} {t('of')} {sorted.length.toLocaleString()}
        </div>

        <div className="pagination-controls">
          <button
            className="page-btn"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            aria-label={t('prev')}
          >
            <FiChevronLeft />
          </button>

          {getPageNumbers().map((p, i) =>
            p === '...' ? (
              <span key={`dots-${i}`} className="page-dots">…</span>
            ) : (
              <button
                key={p}
                className={`page-btn ${page === p ? 'page-active' : ''}`}
                onClick={() => setPage(p)}
              >
                {p}
              </button>
            )
          )}

          <button
            className="page-btn"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            aria-label={t('next')}
          >
            <FiChevronRight />
          </button>
        </div>

        <div className="per-page-select">
          <select
            value={perPage}
            onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1); }}
            id="per-page-select"
          >
            {[10, 25, 50, 100].map(n => (
              <option key={n} value={n}>{n} / {t('page')}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
