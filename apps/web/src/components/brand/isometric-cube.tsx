import React from 'react';

interface IsometricCubeProps {
  readonly className?: string;
  readonly size?: number;
}

export function IsometricCube({ className = '', size = 140 }: IsometricCubeProps) {
  return (
    <div className={`relative flex items-center justify-center ${className}`} style={{ width: size, height: size }}>
      <svg
        viewBox="0 0 160 160"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full drop-shadow-[0_0_24px_rgba(120,177,138,0.18)]"
      >
        <defs>
          {/* Core glow */}
          <radialGradient id="cubeCoreGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#78B18A" stopOpacity="0.8" />
            <stop offset="60%" stopColor="#E5A952" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#78B18A" stopOpacity="0" />
          </radialGradient>

          {/* Top plane gradient */}
          <linearGradient id="topPlaneGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#78B18A" stopOpacity="0.08" />
          </linearGradient>

          {/* Left plane gradient */}
          <linearGradient id="leftPlaneGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#78B18A" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#151918" stopOpacity="0.6" />
          </linearGradient>

          {/* Right plane gradient */}
          <linearGradient id="rightPlaneGrad" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#E5A952" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#0D1010" stopOpacity="0.7" />
          </linearGradient>
        </defs>

        {/* Ambient background wireframe layer */}
        <path
          d="M80 15 L140 50 L80 85 L20 50 Z"
          stroke="#78B18A"
          strokeWidth="1"
          strokeOpacity="0.2"
          fill="none"
        />
        <path
          d="M80 145 L140 110 L80 75 L20 110 Z"
          stroke="#78B18A"
          strokeWidth="1"
          strokeOpacity="0.15"
          fill="none"
        />

        {/* Bottom Glass Platform */}
        <polygon
          points="80,105 135,75 80,45 25,75"
          fill="url(#topPlaneGrad)"
          stroke="#78B18A"
          strokeWidth="1"
          strokeOpacity="0.35"
        />
        <polygon
          points="25,75 80,105 80,118 25,88"
          fill="url(#leftPlaneGrad)"
          stroke="#78B18A"
          strokeWidth="1"
          strokeOpacity="0.3"
        />
        <polygon
          points="80,105 135,75 135,88 80,118"
          fill="url(#rightPlaneGrad)"
          stroke="#78B18A"
          strokeWidth="1"
          strokeOpacity="0.2"
        />

        {/* Middle Glowing Energy Core */}
        <circle cx="80" cy="72" r="28" fill="url(#cubeCoreGlow)" />

        {/* Inner Solid Floating Cube */}
        <polygon
          points="80,68 104,54 80,40 56,54"
          fill="#A8D6B7"
          fillOpacity="0.9"
        />
        <polygon
          points="56,54 80,68 80,90 56,76"
          fill="#5C9E71"
          fillOpacity="0.85"
        />
        <polygon
          points="80,68 104,54 104,76 80,90"
          fill="#3E7851"
          fillOpacity="0.85"
        />

        {/* Top Suspended Glass Shield Plane */}
        <polygon
          points="80,55 130,28 80,2 30,28"
          fill="url(#topPlaneGrad)"
          stroke="#FFFFFF"
          strokeWidth="1.2"
          strokeOpacity="0.45"
        />
        <polygon
          points="30,28 80,55 80,62 30,35"
          fill="url(#leftPlaneGrad)"
          stroke="#78B18A"
          strokeWidth="1"
          strokeOpacity="0.3"
        />
        <polygon
          points="80,55 130,28 130,35 80,62"
          fill="url(#rightPlaneGrad)"
          stroke="#E5A952"
          strokeWidth="1"
          strokeOpacity="0.25"
        />

        {/* Subtly connected light vertices */}
        <line x1="80" y1="2" x2="80" y2="145" stroke="#78B18A" strokeWidth="0.8" strokeDasharray="3 3" strokeOpacity="0.3" />
        <circle cx="80" cy="2" r="2" fill="#FFFFFF" fillOpacity="0.8" />
        <circle cx="130" cy="28" r="2" fill="#78B18A" fillOpacity="0.8" />
        <circle cx="30" cy="28" r="2" fill="#78B18A" fillOpacity="0.8" />
      </svg>
    </div>
  );
}
