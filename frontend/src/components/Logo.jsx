export default function Logo({ size = 40, className = "" }) {
  const id = "mbLogoGrad";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      className={className}
      role="img"
      aria-label="MediBridge logo"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#0ea5e9" />
          <stop offset="1" stopColor="#075985" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="13" fill={`url(#${id})`} />
      <rect
        x="2.5"
        y="2.5"
        width="43"
        height="43"
        rx="12.5"
        stroke="rgba(255,255,255,0.5)"
        strokeWidth="1"
      />
      <path
        d="M6 29h9.5l2.2-5.4 4.4 12.4 3.6-10.6 2.2 3.6h5.1l3.9-6.6 1.9 3.4h3.1"
        stroke="#ffffff"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="22.4" cy="18.6" r="1.8" fill="#ffffff" />
    </svg>
  );
}