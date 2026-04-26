import { scoreColor } from '@/lib/utils';

interface ScoreRingProps {
  value: number; // 0–1
  label: string;
  size?: number;
  strokeWidth?: number;
}

export function ScoreRing({
  value,
  label,
  size = 80,
  strokeWidth = 6,
}: ScoreRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = circumference * Math.min(1, Math.max(0, value));
  const color = scoreColor(value);

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {/* Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={strokeWidth}
          />
          {/* Progress */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={`${dash} ${circumference}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: 'stroke-dasharray 0.8s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className="font-display font-bold text-lg"
            style={{ color }}
          >
            {Math.round(value * 100)}
            <span className="text-xs">%</span>
          </span>
        </div>
      </div>
      <span className="text-xs text-text-secondary font-medium">{label}</span>
    </div>
  );
}
