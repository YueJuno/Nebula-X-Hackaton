import type { Footprint, Instance } from "../types/scheduling";

export default function NetworkPreview({ instance, footprint }: { instance: Instance; footprint?: Footprint }) {
  return (
    <div className="network-scroll">
      <svg viewBox={`0 0 1000 ${instance.lines.length * 150 + 30}`} role="img" aria-label="Railway network; highlighted stations belong to the selected activity's occupied span">
        {instance.lines.map((line, index) => {
          const stations = instance.stations.filter(s => s.line_code === line.line_code).sort((a, b) => a.seq - b.seq);
          const y = 65 + index * 150;
          return <g key={line.line_code}>
            <text x="35" y={y - 30} fill="#23486f" fontSize="18" fontWeight="600">{line.line_name}</text>
            <line x1="70" x2="930" y1={y} y2={y} stroke={index === 0 ? "#3262a0" : "#24817a"} strokeWidth="6" />
            {stations.map((station, position) => {
              const x = 70 + position * 860 / Math.max(1, stations.length - 1);
              const selected = footprint?.occupied.some(id => id.startsWith(`PLAT:${line.line_code}:${station.station_id}:`));
              return <g key={station.station_id}>
                <circle cx={x} cy={y} r={station.is_interchange ? 12 : 8} fill={selected ? "#f6b644" : "white"} stroke="#23486f" strokeWidth="3" />
                <text x={x} y={y + 35} textAnchor="middle" fontSize="15">{station.station_id}</text>
              </g>;
            })}
          </g>;
        })}
      </svg>
      <p className="note">Network preview, not a booked schedule. Gold marks the selected activity's station span; bound-specific locations appear below.</p>
    </div>
  );
}
