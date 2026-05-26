
interface Props {
  bodyClass?: string;
  vehicleType?: string;
  color: string;
  className?: string;
}

export const CAR_COLORS = [
  { name: 'White',  hex: '#f8fafc' },
  { name: 'Silver', hex: '#94a3b8' },
  { name: 'Gray',   hex: '#475569' },
  { name: 'Black',  hex: '#1e293b' },
  { name: 'Red',    hex: '#dc2626' },
  { name: 'Maroon', hex: '#7f1d1d' },
  { name: 'Blue',   hex: '#2563eb' },
  { name: 'Navy',   hex: '#1e3a5f' },
  { name: 'Green',  hex: '#16a34a' },
  { name: 'Brown',  hex: '#92400e' },
  { name: 'Gold',   hex: '#ca8a04' },
  { name: 'Orange', hex: '#ea580c' },
];

export const DEFAULT_COLOR = '#475569';

const LIGHT_COLORS = new Set([
  '#f8fafc', '#e2e8f0', '#f1f5f9', '#cbd5e1', 'white', '#ffffff',
]);

const GLASS = 'rgba(15,23,42,0.6)';
const WHEEL_OUTER = '#0f172a';
const WHEEL_RIM = '#1e293b';
const WHEEL_HUB = '#334155';

type BodyType = 'sedan' | 'suv' | 'truck' | 'van' | 'trailer';

function detectBodyType(bodyClass?: string, vehicleType?: string): BodyType {
  if (vehicleType === 'trailer') return 'trailer';
  const bc = (bodyClass ?? '').toLowerCase();
  if (bc.includes('pickup') || bc.includes('truck')) return 'truck';
  if (bc.includes('van') || bc.includes('minivan') || bc.includes('bus')) return 'van';
  if (
    bc.includes('sport utility') ||
    bc.includes('suv') ||
    bc.includes('mpv') ||
    bc.includes('crossover') ||
    bc.includes('wagon')
  ) return 'suv';
  return 'sedan';
}

function Wheel({ cx, cy, r }: { cx: number; cy: number; r: number }) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} fill={WHEEL_OUTER} />
      <circle cx={cx} cy={cy} r={r * 0.65} fill={WHEEL_RIM} />
      <circle cx={cx} cy={cy} r={r * 0.32} fill={WHEEL_HUB} />
    </g>
  );
}

function bodyProps(color: string) {
  const isLight = LIGHT_COLORS.has(color.toLowerCase());
  return isLight
    ? { fill: color, stroke: '#94a3b8', strokeWidth: 1.5 }
    : { fill: color };
}

function Sedan({ color }: { color: string }) {
  const bp = bodyProps(color);
  return (
    <g>
      <rect x={10} y={60} width={280} height={22} rx={4} {...bp} />
      <path d="M80,60 L98,22 L202,22 L220,60 Z" {...bp} />
      <path d="M100,57 L114,25 L148,25 L148,57 Z" fill={GLASS} />
      <path d="M152,57 L152,25 L186,25 L200,57 Z" fill={GLASS} />
      <Wheel cx={68} cy={84} r={17} />
      <Wheel cx={232} cy={84} r={17} />
    </g>
  );
}

function SUV({ color }: { color: string }) {
  const bp = bodyProps(color);
  return (
    <g>
      <rect x={10} y={58} width={280} height={24} rx={4} {...bp} />
      <path d="M58,58 L66,18 L234,18 L242,58 Z" {...bp} />
      <path d="M68,54 L75,21 L145,21 L145,54 Z" fill={GLASS} />
      <path d="M155,54 L155,21 L225,21 L232,54 Z" fill={GLASS} />
      <Wheel cx={70} cy={84} r={19} />
      <Wheel cx={230} cy={84} r={19} />
    </g>
  );
}

function Truck({ color }: { color: string }) {
  const bp = bodyProps(color);
  return (
    <g>
      <rect x={8} y={58} width={155} height={24} rx={3} {...bp} />
      <path d="M38,58 L54,22 L155,22 L155,58 Z" {...bp} />
      <path d="M56,54 L70,25 L148,25 L148,54 Z" fill={GLASS} />
      <rect x={168} y={52} width={124} height={30} rx={3} {...bp} />
      <rect x={172} y={56} width={116} height={6} fill={GLASS} />
      <Wheel cx={68} cy={84} r={18} />
      <Wheel cx={230} cy={84} r={18} />
    </g>
  );
}

function Van({ color }: { color: string }) {
  const bp = bodyProps(color);
  return (
    <g>
      <rect x={10} y={18} width={268} height={64} rx={6} {...bp} />
      <path d="M16,78 L16,30 Q18,22 44,20 L54,20 L54,78 Z" fill={GLASS} />
      <rect x={60} y={24} width={168} height={34} rx={3} fill={GLASS} />
      <Wheel cx={72} cy={84} r={17} />
      <Wheel cx={232} cy={84} r={17} />
    </g>
  );
}

function Trailer({ color }: { color: string }) {
  const bp = bodyProps(color);
  return (
    <g>
      <rect x={4} y={54} width={22} height={10} rx={3} fill={WHEEL_RIM} />
      <rect x={22} y={22} width={266} height={54} rx={4} {...bp} />
      <rect x={38} y={76} width={8} height={14} rx={2} fill={WHEEL_RIM} />
      <Wheel cx={214} cy={86} r={14} />
      <Wheel cx={250} cy={86} r={14} />
    </g>
  );
}

export default function VehicleSilhouette({ bodyClass, vehicleType, color, className }: Props) {
  const type = detectBodyType(bodyClass, vehicleType);

  return (
    <svg viewBox="0 0 300 100" xmlns="http://www.w3.org/2000/svg" className={className}>
      {type === 'sedan'   && <Sedan   color={color} />}
      {type === 'suv'     && <SUV     color={color} />}
      {type === 'truck'   && <Truck   color={color} />}
      {type === 'van'     && <Van     color={color} />}
      {type === 'trailer' && <Trailer color={color} />}
    </svg>
  );
}
