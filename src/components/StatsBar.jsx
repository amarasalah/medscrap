'use client';
import { useLanguage } from '@/contexts/LanguageContext';
import { FiUsers, FiHome, FiMapPin, FiActivity } from 'react-icons/fi';
import { useEffect, useState, useRef } from 'react';

function AnimatedNumber({ target, duration = 1200 }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const animated = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !animated.current) {
          animated.current = true;
          const start = performance.now();
          const step = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.floor(eased * target));
            if (progress < 1) requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        }
      },
      { threshold: 0.1 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target, duration]);

  return <span ref={ref} className="stat-number">{count.toLocaleString()}</span>;
}

export default function StatsBar({ data }) {
  const { t } = useLanguage();

  const totalPros = data.filter(d => d.type === 'professionnel_de_sante').length;
  const totalInst = data.filter(d => d.type === 'health_institution').length;
  const cities = new Set();
  data.forEach(d => (d.addresses || []).forEach(a => a.city && cities.add(a.city)));

  const stats = [
    { icon: <FiActivity />, label: t('totalRecords'), value: data.length, color: 'var(--accent-1)' },
    { icon: <FiUsers />, label: t('professionals'), value: totalPros, color: 'var(--accent-2)' },
    { icon: <FiHome />, label: t('institutions'), value: totalInst, color: 'var(--accent-3)' },
    { icon: <FiMapPin />, label: t('cities'), value: cities.size, color: 'var(--accent-4)' },
  ];

  return (
    <div className="stats-bar">
      {stats.map((stat, i) => (
        <div key={i} className="stat-card" style={{ '--stat-color': stat.color }}>
          <div className="stat-icon">{stat.icon}</div>
          <div className="stat-info">
            <AnimatedNumber target={stat.value} />
            <span className="stat-label">{stat.label}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
