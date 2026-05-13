'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { FiGlobe } from 'react-icons/fi';
import { RiStethoscopeLine } from 'react-icons/ri';

export default function Header() {
  const { lang, toggleLang, t } = useLanguage();

  return (
    <header className="header">
      <div className="header-inner">
        <div className="header-brand">
          <div className="header-logo">
            <RiStethoscopeLine className="logo-icon" />
          </div>
          <div>
            <h1 className="header-title">{t('appName')}</h1>
            <p className="header-subtitle">{t('subtitle')}</p>
          </div>
        </div>
        <button
          className="lang-toggle"
          onClick={toggleLang}
          title={lang === 'fr' ? 'Switch to English' : 'Passer en Français'}
          id="lang-toggle-btn"
        >
          <FiGlobe />
          <span>{lang === 'fr' ? 'EN' : 'FR'}</span>
        </button>
      </div>
    </header>
  );
}
