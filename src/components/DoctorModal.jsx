'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { useEffect, useRef } from 'react';
import { FiX, FiPhone, FiMapPin, FiExternalLink, FiMap, FiTag, FiUser, FiHome } from 'react-icons/fi';
import { RiStethoscopeLine } from 'react-icons/ri';

export default function DoctorModal({ doctor, onClose }) {
  const { t } = useLanguage();
  const overlayRef = useRef(null);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  if (!doctor) return null;

  const isPro = doctor.type === 'professionnel_de_sante';

  return (
    <div
      className="modal-overlay"
      ref={overlayRef}
      onClick={(e) => e.target === overlayRef.current && onClose()}
    >
      <div className="modal-content" role="dialog" aria-modal="true">
        <button className="modal-close" onClick={onClose} aria-label={t('close')} id="modal-close-btn">
          <FiX />
        </button>

        {/* Header */}
        <div className="modal-header">
          <div className={`modal-type-badge ${isPro ? 'badge-pro' : 'badge-inst'}`}>
            {isPro ? <FiUser /> : <FiHome />}
            <span>{isPro ? t('professional') : t('institution')}</span>
          </div>
          <h2 className="modal-name">{doctor.name}</h2>
          {doctor.specialty && (
            <div className="modal-specialty">
              <RiStethoscopeLine />
              <span>{doctor.specialty}</span>
            </div>
          )}
        </div>

        {/* Details grid */}
        <div className="modal-details">
          {doctor.subSpecialty && (
            <div className="detail-row">
              <div className="detail-icon"><FiTag /></div>
              <div className="detail-content">
                <span className="detail-label">{t('subSpecialty')}</span>
                <span className="detail-value">{doctor.subSpecialty}</span>
              </div>
            </div>
          )}

          <div className="detail-row">
            <div className="detail-icon"><FiMapPin /></div>
            <div className="detail-content">
              <span className="detail-label">{t('address')}</span>
              <span className="detail-value">{doctor.address || t('noAddress')}</span>
              {doctor.city && (
                <span className="detail-sub">
                  {doctor.city}{doctor.postalCode ? ` · ${doctor.postalCode}` : ''}
                  {doctor.department ? ` · ${doctor.department}` : ''}
                </span>
              )}
              {doctor.region && (
                <span className="detail-sub">{doctor.region}</span>
              )}
            </div>
          </div>

          <div className="detail-row">
            <div className="detail-icon"><FiPhone /></div>
            <div className="detail-content">
              <span className="detail-label">{t('phone')}</span>
              {doctor.phone ? (
                <a href={`tel:${doctor.phoneRaw}`} className="detail-phone">{doctor.phone}</a>
              ) : (
                <span className="detail-value muted">{t('noPhone')}</span>
              )}
            </div>
          </div>

          {doctor.convention && (
            <div className="detail-row">
              <div className="detail-icon"><FiTag /></div>
              <div className="detail-content">
                <span className="detail-label">{t('convention')}</span>
                <span className={`convention-badge-lg ${doctor.convention.includes('1') ? 'conv-1' : 'conv-2'}`}>
                  {doctor.convention}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="modal-actions">
          {doctor.profileUrl && (
            <a
              href={doctor.profileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="modal-btn modal-btn-primary"
              id="modal-profile-link"
            >
              <FiExternalLink />
              {t('profile')}
            </a>
          )}
          {doctor.mapsUrl && (
            <a
              href={doctor.mapsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="modal-btn modal-btn-secondary"
              id="modal-maps-link"
            >
              <FiMap />
              {t('directions')}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
