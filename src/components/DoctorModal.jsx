'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { useEffect, useRef } from 'react';
import { FiX, FiPhone, FiMapPin, FiExternalLink, FiMap, FiTag, FiUser, FiHome, FiMail } from 'react-icons/fi';
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
  const addresses = doctor.addresses || [];
  const phones = doctor.phones || [];
  const primaryMaps = addresses.find(a => a.mapsUrl)?.mapsUrl;

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

          {addresses.length === 0 && (
            <div className="detail-row">
              <div className="detail-icon"><FiMapPin /></div>
              <div className="detail-content">
                <span className="detail-label">{t('address')}</span>
                <span className="detail-value muted">{t('noAddress')}</span>
              </div>
            </div>
          )}

          {addresses.map((a, i) => (
            <div className="detail-row" key={`addr-${i}`}>
              <div className="detail-icon"><FiMapPin /></div>
              <div className="detail-content">
                <span className="detail-label">
                  {addresses.length > 1 ? `${t('address')} ${i + 1}` : t('address')}
                </span>
                <span className="detail-value">{a.address || t('noAddress')}</span>
                {a.city && (
                  <span className="detail-sub">
                    {a.city}{a.postalCode ? ` · ${a.postalCode}` : ''}
                    {a.department ? ` · ${a.department}` : ''}
                  </span>
                )}
                {a.region && <span className="detail-sub">{a.region}</span>}
              </div>
            </div>
          ))}

          {phones.length === 0 ? (
            <div className="detail-row">
              <div className="detail-icon"><FiPhone /></div>
              <div className="detail-content">
                <span className="detail-label">{t('phone')}</span>
                <span className="detail-value muted">{t('noPhone')}</span>
              </div>
            </div>
          ) : (
            phones.map((p, i) => (
              <div className="detail-row" key={`ph-${i}`}>
                <div className="detail-icon"><FiPhone /></div>
                <div className="detail-content">
                  <span className="detail-label">
                    {phones.length > 1 ? `${t('phone')} ${i + 1}` : t('phone')}
                  </span>
                  <a href={`tel:${p.raw}`} className="detail-phone">{p.formatted}</a>
                </div>
              </div>
            ))
          )}

          {doctor.email && (
            <div className="detail-row">
              <div className="detail-icon"><FiMail /></div>
              <div className="detail-content">
                <span className="detail-label">{t('email')}</span>
                <a href={`mailto:${doctor.email}`} className="detail-phone">{doctor.email}</a>
              </div>
            </div>
          )}

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
          {primaryMaps && (
            <a
              href={primaryMaps}
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
