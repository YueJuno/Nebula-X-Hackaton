export default function RailGraphic() {
  return (
    <svg className="rail-graphic" viewBox="0 0 620 180" role="img" aria-label="MRT train connecting the rail network">
      <g fill="none" strokeWidth="3" strokeLinecap="round">
        <path d="M0 62h150q30 0 50 20l20 20h60m60 0h60l20-20q20-20 50-20h150" stroke="#becbbd" />
        <path d="M0 112h145q20 0 40-20l10-10q20-20 40-20h45m60 0h45q20 0 40 20l10 10q20 20 40 20h145" stroke="#d9c7a6" />
        <path d="M50 146h125q25 0 50-25l20-20h130l20 20q25 25 50 25h125" stroke="#b6cbd0" />
      </g>
      <g fill="#fafaf8" stroke="#a4b6a2" strokeWidth="2"><circle cx="95" cy="62" r="5" /><circle cx="525" cy="62" r="5" /><circle cx="145" cy="112" r="5" /><circle cx="475" cy="112" r="5" /><circle cx="175" cy="146" r="5" /><circle cx="445" cy="146" r="5" /></g>
      <ellipse cx="310" cy="163" rx="76" ry="8" fill="#e9ece4" />
      <g stroke="#3c5e4b" strokeWidth="2.5" strokeLinejoin="round">
        <path d="m275 137-12 30m82-30 12 30m-87-10h80" fill="none" />
        <rect x="252" y="18" width="116" height="126" rx="28" fill="#fafaf8" />
        <rect x="264" y="51" width="92" height="45" rx="12" fill="#e0e8dc" />
        <path d="M310 51v45" />
        <path d="M253 110h114" stroke="#81a28b" strokeWidth="9" />
        <circle cx="275" cy="127" r="4" fill="#dbc8a4" /><circle cx="345" cy="127" r="4" fill="#dbc8a4" />
      </g>
      <rect x="288" y="31" width="44" height="8" rx="4" fill="#3c5e4b" />
      <path d="m273 58 13 0-14 23" fill="none" stroke="#fafaf8" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
