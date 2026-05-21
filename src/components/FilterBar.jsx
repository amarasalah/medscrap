'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { useMemo } from 'react';
import { FiSearch, FiX, FiFilter } from 'react-icons/fi';
import { COUNTRY_LABELS } from '@/lib/doctor';

function uniqueFromAddresses(data, field, parentFilter) {
  const set = new Set();
  for (const d of data) {
    if (parentFilter && !parentFilter(d)) continue;
    for (const a of d.addresses || []) {
      if (a[field]) set.add(a[field]);
    }
  }
  return [...set].sort();
}

export default function FilterBar({ data, filters, setFilters, filteredCount }) {
  const { t } = useLanguage();

  const countries = useMemo(() => {
    const set = new Set(data.map(d => d.country).filter(Boolean));
    return [...set].sort();
  }, [data]);

  const scoped = useMemo(() => {
    return filters.country ? data.filter(d => d.country === filters.country) : data;
  }, [data, filters.country]);

  const regions = useMemo(() => uniqueFromAddresses(scoped, 'region'), [scoped]);

  const departments = useMemo(() => {
    const inRegion = filters.region
      ? (d) => (d.addresses || []).some(a => a.region === filters.region)
      : null;
    return uniqueFromAddresses(scoped, 'department', inRegion);
  }, [scoped, filters.region]);

  const cities = useMemo(() => {
    const matches = (d) => {
      if (filters.region && !(d.addresses || []).some(a => a.region === filters.region)) return false;
      if (filters.department && !(d.addresses || []).some(a => a.department === filters.department)) return false;
      return true;
    };
    return uniqueFromAddresses(scoped, 'city', matches);
  }, [scoped, filters.region, filters.department]);

  const specialties = useMemo(() => {
    const set = new Set(scoped.map(d => d.specialty).filter(Boolean));
    return [...set].sort();
  }, [scoped]);

  const conventions = useMemo(() => {
    const set = new Set(scoped.map(d => d.convention).filter(Boolean));
    return [...set].sort();
  }, [scoped]);

  const activeFilterCount = useMemo(() => {
    return Object.values(filters).filter(v => v && v !== '').length;
  }, [filters]);

  const handleChange = (key, value) => {
    const newFilters = { ...filters, [key]: value };
    if (key === 'country') {
      newFilters.region = '';
      newFilters.department = '';
      newFilters.city = '';
      newFilters.convention = '';
    }
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
      country: '',
      region: '',
      department: '',
      city: '',
      specialty: '',
      type: '',
      convention: '',
      search: '',
    });
  };

  const showConvention = !filters.country || filters.country === 'FR';

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
        {countries.length > 1 && (
          <div className="filter-group">
            <label htmlFor="filter-country">{t('country')}</label>
            <select
              id="filter-country"
              value={filters.country}
              onChange={(e) => handleChange('country', e.target.value)}
            >
              <option value="">{t('allCountries')}</option>
              {countries.map(c => <option key={c} value={c}>{COUNTRY_LABELS[c] || c}</option>)}
            </select>
          </div>
        )}

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

        {showConvention && (
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
        )}

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
