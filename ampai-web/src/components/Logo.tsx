import React from 'react';

interface LogoProps {
  className?: string;
}

export const Logo: React.FC<LogoProps> = ({ className = 'logo-svg' }) => {
  return (
    <svg 
      className={className}
      viewBox="0 0 100 100" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        {/* Vibrant gradient matching favicon */}
        <linearGradient id="logoPrimaryGlow" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#00f2fe" />
          <stop offset="100%" stop-color="#4facfe" />
        </linearGradient>
        <linearGradient id="logoAccentGlow" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#00f2fe" />
          <stop offset="100%" stop-color="#10b981" />
        </linearGradient>
      </defs>

      {/* Connection outline */}
      <path 
        d="M 30,50 L 50,30 L 70,50 L 50,70 Z" 
        fill="none" 
        stroke="url(#logoPrimaryGlow)" 
        strokeWidth="3" 
        opacity="0.3" 
      />
      <line x1="50" y1="15" x2="50" y2="85" stroke="url(#logoAccentGlow)" strokeWidth="2" strokeDasharray="3,3" opacity="0.5" />
      <line x1="15" y1="50" x2="85" y2="50" stroke="url(#logoAccentGlow)" strokeWidth="2" strokeDasharray="3,3" opacity="0.5" />

      {/* Outer ring segment representing intelligence layers */}
      <circle 
        cx="50" 
        cy="50" 
        r="38" 
        fill="none" 
        stroke="url(#logoPrimaryGlow)" 
        strokeWidth="4" 
        strokeLinecap="round" 
        strokeDasharray="200, 40" 
      />
      <circle cx="50" cy="50" r="44" fill="none" stroke="url(#logoAccentGlow)" strokeWidth="1" opacity="0.6" strokeDasharray="5, 10" />

      {/* Node points */}
      <circle cx="50" cy="15" r="5" fill="#10b981" />
      <circle cx="50" cy="85" r="5" fill="#00f2fe" />
      <circle cx="15" cy="50" r="5" fill="#4facfe" />
      <circle cx="85" cy="50" r="5" fill="#10b981" />

      {/* Central CLI / Brain Prompt */}
      <g transform="translate(33, 33) scale(0.72)">
        {/* Terminal Command Arrow (>) */}
        <path 
          d="M12 8 L28 20 L12 32" 
          fill="none" 
          stroke="url(#logoPrimaryGlow)" 
          strokeWidth="7" 
          strokeLinecap="round" 
          strokeLinejoin="round" 
        />
        {/* Underscore Cursor (_) */}
        <line 
          x1="32" 
          y1="32" 
          x2="48" 
          y2="32" 
          stroke="#10b981" 
          strokeWidth="7" 
          strokeLinecap="round" 
        />
      </g>
    </svg>
  );
};
