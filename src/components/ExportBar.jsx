'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { FiDownload } from 'react-icons/fi';
import { exportToExcel } from '@/lib/exportExcel';

export default function ExportBar({ filteredData, allData }) {
  const { t } = useLanguage();

  return (
    <div className="export-bar">
      <button
        className="export-btn export-btn-primary"
        onClick={() => exportToExcel(filteredData, 'ScrapDoc_Filtered')}
        disabled={filteredData.length === 0}
        id="export-filtered-btn"
      >
        <FiDownload />
        {t('exportFiltered')} ({filteredData.length.toLocaleString()})
      </button>
      <button
        className="export-btn export-btn-secondary"
        onClick={() => exportToExcel(allData, 'ScrapDoc_All')}
        id="export-all-btn"
      >
        <FiDownload />
        {t('exportAll')} ({allData.length.toLocaleString()})
      </button>
    </div>
  );
}
