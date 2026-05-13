'use client';
import { useState, useMemo, useEffect } from 'react';
import Header from '@/components/Header';
import StatsBar from '@/components/StatsBar';
import FilterBar from '@/components/FilterBar';
import ResultsTable from '@/components/ResultsTable';
import DoctorModal from '@/components/DoctorModal';
import ExportBar from '@/components/ExportBar';

export default function Home() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [filters, setFilters] = useState({
    region: '',
    department: '',
    city: '',
    specialty: '',
    type: '',
    convention: '',
    search: '',
  });

  // Load data from JSON
  useEffect(() => {
    fetch('/doctors.json')
      .then(res => res.json())
      .then(jsonData => {
        setData(jsonData);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load data:', err);
        setLoading(false);
      });
  }, []);

  // Apply filters
  const filteredData = useMemo(() => {
    let result = data;

    if (filters.region) {
      result = result.filter(d => d.region === filters.region);
    }
    if (filters.department) {
      result = result.filter(d => d.department === filters.department);
    }
    if (filters.city) {
      result = result.filter(d => d.city === filters.city);
    }
    if (filters.specialty) {
      result = result.filter(d => d.specialty === filters.specialty);
    }
    if (filters.type) {
      result = result.filter(d => d.type === filters.type);
    }
    if (filters.convention) {
      result = result.filter(d => d.convention === filters.convention);
    }
    if (filters.search) {
      const q = filters.search.toLowerCase();
      result = result.filter(d =>
        (d.name || '').toLowerCase().includes(q) ||
        (d.address || '').toLowerCase().includes(q) ||
        (d.phone || '').includes(q)
      );
    }

    return result;
  }, [data, filters]);

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-pulse" />
        <p className="loading-text">Chargement des données...</p>
      </div>
    );
  }

  return (
    <main className="main-container">
      <Header />
      <div className="content-wrapper">
        <StatsBar data={data} />
        <FilterBar
          data={data}
          filters={filters}
          setFilters={setFilters}
          filteredCount={filteredData.length}
        />
        <ExportBar filteredData={filteredData} allData={data} />
        <ResultsTable data={filteredData} onSelect={setSelectedDoctor} />
      </div>

      {selectedDoctor && (
        <DoctorModal
          doctor={selectedDoctor}
          onClose={() => setSelectedDoctor(null)}
        />
      )}
    </main>
  );
}
