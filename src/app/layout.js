import { Inter } from 'next/font/google';
import './globals.css';
import { LanguageProvider } from '@/contexts/LanguageContext';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

export const metadata = {
  title: 'ScrapDoc — Annuaire des Professionnels de Santé',
  description: 'Explorez et filtrez plus de 3000 professionnels et établissements de santé en France. Recherchez par région, département, ville, spécialité et plus encore.',
  keywords: ['médecins', 'santé', 'annuaire', 'France', 'urologues', 'doctors', 'healthcare'],
};

export default function RootLayout({ children }) {
  return (
    <html lang="fr" className={inter.variable}>
      <body>
        <LanguageProvider>
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}
