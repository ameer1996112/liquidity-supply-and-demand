import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'TradeOps Dashboard',
    short_name: 'TradeOps',
    description: 'Professional trading operations dashboard with AI Copilot',
    start_url: '/',
    display: 'standalone',
    background_color: '#0b0e14',
    theme_color: '#0b0e14',
    orientation: 'portrait-primary',
    icons: [
      {
        src: '/favicon.ico',
        sizes: '48x48',
        type: 'image/x-icon',
        purpose: 'any',
      },
    ],
    shortcuts: [
      {
        name: 'Dashboard',
        url: '/',
        description: 'Open main dashboard',
      },
      {
        name: 'Journal',
        url: '/journal',
        description: 'Open trade journal',
      },
      {
        name: 'Risk Monitor',
        url: '/risk',
        description: 'Open risk monitor',
      },
      {
        name: 'Prop Firm Hub',
        url: '/prop-firm',
        description: 'Open Prop Firm Hub',
      },
    ],
    categories: ['finance', 'productivity'],
  };
}
