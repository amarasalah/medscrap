'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { useMemo } from 'react';
import { FiSearch, FiX, FiFilter } from 'react-icons/fi';

export default function FilterBar({ data, filters, setFilters, filteredCount }) {
  const { t } = useLanguage();

  // Compute unique values for dropdowns, respecting cascading
  const regions = useMemo(() => {
    const set = new Set(data.map(d => d.region).filter(Boolean));
    return [...set].sort();
  }, [data]);

  const departments = useMemo(() => {
    let subset = data;
    if (filters.region) subset = subset.filter(d => d.region === filters.region);
    const set = new Set(subset.map(d => d.department).filter(Boolean));
    return [...set].sort();
  }, [data, filters.region]);

  const cities = useMemo(() => {
    let subset = data;
    if (filters.region) subset = subset.filter(d => d.region === filters.region);
    if (filters.department) subset = subset.filter(d => d.department === filters.department);
    const set = new Set(subset.map(d => d.city).filter(Boolean));
    return [...set].sort();
  }, [data, filters.region, filters.department]);

  const specialties = useMemo(() => {
    const set = new Set(data.map(d => d.specialty).filter(Boolean));
    return [...set].sort();
  }, [data]);

  const conventions = useMemo(() => {
    const set = new Set(data.map(d => d.convention).filter(Boolean));
    return [...set].sort();
  }, [data]);

  const activeFilterCount = useMemo(() => {
    return Object.values(filters).filter(v => v && v !== '').length;
  }, [filters]);

  const handleChange = (key, value) => {
    const newFilters = { ...filters, [key]: value };
    // Cascade: reset children when parent changes
    if (key === 'region') {
      newFilters.department = '';
      newFilters.city = '';
    }
    if (key === 'department') {
      newFilters.city = '';
    }
    setFilters(newFilters);
  };

  const clearAll = () => {
    setFilters({
      region: '',
      department: '',
      city: '',
      specialty: '',
      type: '',
      convention: '',
      search: '',
    });
  };

  return (
    <div className="filter-bar">
      <div className="filter-header">
        <div className="filter-title">
          <FiFilter />
          <span>Filtres / Filters</span>
          {activeFilterCount > 0 && (
            <span className="filter-badge">{activeFilterCount}</span>
          )}
        </div>
        <div className="filter-result-count">
          {filteredCount.toLocaleString()} {t('results')}
        </div>
      </div>

      <div className="filter-grid">
        <div className="filter-group">
          <label htmlFor="filter-region">{t('region')}</label>
          <select
            id="filter-region"
            value={filters.region}
            onChange={(e) => handleChange('region', e.target.value)}
          >
            <option value="">{t('allRegions')}</option>
            {regions.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-department">{t('department')}</label>
          <select
            id="filter-department"
            value={filters.department}
            onChange={(e) => handleChange('department', e.target.value)}
          >
            <option value="">{t('allDepartments')}</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-city">{t('city')}</label>
          <select
            id="filter-city"
            value={filters.city}
            onChange={(e) => handleChange('city', e.target.value)}
          >
            <option value="">{t('allCities')}</option>
            {cities.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-specialty">{t('specialty')}</label>
          <select
            id="filter-specialty"
            value={filters.specialty}
            onChange={(e) => handleChange('specialty', e.target.value)}
          >
            <option value="">{t('allSpecialties')}</option>
            {specialties.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-type">{t('type')}</label>
          <select
            id="filter-type"
            value={filters.type}
            onChange={(e) => handleChange('type', e.target.value)}
          >
            <option value="">{t('allTypes')}</option>
            <option value="professionnel_de_sante">{t('professional')}</option>
            <option value="health_institution">{t('institution')}</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-convention">{t('convention')}</label>
          <select
            id="filter-convention"
            value={filters.convention}
            onChange={(e) => handleChange('convention', e.target.value)}
          >
            <option value="">{t('allConventions')}</option>
            {conventions.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="filter-group filter-search-group">
          <label htmlFor="filter-search">{t('name')}</label>
          <div className="search-input-wrap">
            <FiSearch className="search-icon" />
            <input
              type="text"
              id="filter-search"
              placeholder={t('searchPlaceholder')}
              value={filters.search}
              onChange={(e) => handleChange('search', e.target.value)}
            />
            {filters.search && (
              <button
                className="search-clear"
                onClick={() => handleChange('search', '')}
                aria-label="Clear search"
              >
                <FiX />
              </button>
            )}
          </div>
        </div>
      </div>

      {activeFilterCount > 0 && (
        <button className="clear-filters-btn" onClick={clearAll} id="clear-filters-btn">
          <FiX />
          {t('clearFilters')} ({activeFilterCount})
        </button>
      )}
    </div>
  );
}
