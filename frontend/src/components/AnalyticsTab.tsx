import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import type { FuelEntry, MaintenanceEntry, Expense, TripEntry } from '../types';

interface Props {
  isTrailer: boolean;
  isGasoline: boolean;
  loading: boolean;
  fuelEntries: FuelEntry[];
  maintEntries: MaintenanceEntry[];
  expenses: Expense[];
  tripEntries: TripEntry[];
}

const TEAL = '#14b8a6';
const AMBER = '#f59e0b';
const INDIGO = '#6366f1';
const BLUE = '#3b82f6';
const RED = '#ef4444';

const CHART_COLORS = [TEAL, AMBER, INDIGO, BLUE, RED];

const AXIS = { fill: '#94a3b8', fontSize: 11 };
const GRID = '#1e293b';

function fmtMonth(ym: string) {
  const [y, m] = ym.split('-');
  return new Date(Number(y), Number(m) - 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
}

function aggregateByMonth<T extends { date: string }>(
  items: T[],
  getValue: (item: T) => number
): { month: string; value: number }[] {
  const map: Record<string, number> = {};
  for (const item of items) {
    const key = item.date.slice(0, 7);
    map[key] = (map[key] ?? 0) + getValue(item);
  }
  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => ({ month: fmtMonth(k), value: Number(v.toFixed(2)) }));
}

function ChartCard({ title, children, empty }: { title: string; children: React.ReactNode; empty?: boolean }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">{title}</h3>
      {empty ? (
        <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
          Not enough data yet
        </div>
      ) : (
        children
      )}
    </div>
  );
}

const tooltipStyle = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 6, fontSize: 12 },
  labelStyle: { color: '#cbd5e1' },
  itemStyle: { color: '#f1f5f9' },
};

export default function AnalyticsTab({ isTrailer, isGasoline, loading, fuelEntries, maintEntries, expenses, tripEntries }: Props) {
  if (loading) {
    return <div className="text-slate-400 text-center py-16">Loading analytics...</div>;
  }

  // ── Vehicle charts ────────────────────────────────────────────────────────────

  const mpgData = [...fuelEntries]
    .filter((e) => e.mpg != null)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((e) => ({ date: e.date.slice(5), mpg: Number(Number(e.mpg).toFixed(1)) }));

  const monthlyFuelCost = aggregateByMonth(fuelEntries, (e) => e.cost);

  const fuelTotal = fuelEntries.reduce((s, e) => s + Number(e.cost), 0);
  const maintTotal = maintEntries.reduce((s, e) => s + Number(e.cost), 0);
  const expenseTotal = expenses.reduce((s, e) => s + Number(e.amount), 0);
  const costBreakdown = [
    { name: 'Fuel', value: Number(fuelTotal.toFixed(2)) },
    { name: 'Maintenance', value: Number(maintTotal.toFixed(2)) },
    { name: 'Other Expenses', value: Number(expenseTotal.toFixed(2)) },
  ].filter((d) => d.value > 0);

  const monthlyMaintCost = aggregateByMonth(maintEntries, (e) => e.cost);

  // ── Odometer history (vehicles) ───────────────────────────────────────────────

  const odometerData = [...fuelEntries]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((e) => ({ date: e.date.slice(5), mileage: Math.round(e.mileage) }));

  // ── Cost per mile trend ───────────────────────────────────────────────────────

  const costPerMileData = [...fuelEntries]
    .filter((e) => e.cost_per_mile != null)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((e) => ({ date: e.date.slice(5), cpm: Number(Number(e.cost_per_mile).toFixed(4)) }));

  // ── Octane trend (gasoline vehicles only) ─────────────────────────────────────

  const octaneData = [...fuelEntries]
    .filter((e) => e.octane != null)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((e) => ({ date: e.date.slice(5), octane: e.octane! }));

  // ── Trailer charts ────────────────────────────────────────────────────────────

  const monthlyMiles = aggregateByMonth(tripEntries, (e) => e.miles);

  const monthlyTripCount = (() => {
    const map: Record<string, number> = {};
    for (const t of tripEntries) {
      const key = t.date.slice(0, 7);
      map[key] = (map[key] ?? 0) + 1;
    }
    return Object.entries(map)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => ({ month: fmtMonth(k), value: v }));
  })();

  const cumulativeMilesData = (() => {
    const sorted = [...tripEntries].sort((a, b) => a.date.localeCompare(b.date));
    let total = 0;
    return sorted.map((t) => { total += t.miles; return { date: t.date.slice(5), total: Math.round(total) }; });
  })();

  if (isTrailer) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ChartCard title="Monthly Miles Hauled" empty={monthlyMiles.length === 0}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={monthlyMiles} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="month" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toLocaleString()} mi`, 'Miles']} />
              <Bar dataKey="value" fill={BLUE} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Trips per Month" empty={monthlyTripCount.length === 0}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={monthlyTripCount} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="month" tick={AXIS} />
              <YAxis allowDecimals={false} tick={AXIS} />
              <Tooltip {...tooltipStyle} formatter={(v: number) => [v, 'Trips']} />
              <Bar dataKey="value" fill={TEAL} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Monthly Maintenance Cost" empty={monthlyMaintCost.length === 0}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={monthlyMaintCost} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="month" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip {...tooltipStyle} formatter={(v: number) => [`$${v.toFixed(2)}`, 'Cost']} />
              <Bar dataKey="value" fill={AMBER} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Cumulative Miles Hauled" empty={cumulativeMilesData.length < 2}>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={cumulativeMilesData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={AXIS} />
              <YAxis tick={AXIS} />
              <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toLocaleString()} mi`, 'Total Miles']} />
              <Line type="monotone" dataKey="total" stroke={BLUE} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <ChartCard title="MPG Over Time" empty={mpgData.length < 2}>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={mpgData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="date" tick={AXIS} />
            <YAxis tick={AXIS} domain={['auto', 'auto']} />
            <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v} MPG`, 'Fuel Economy']} />
            <Line type="monotone" dataKey="mpg" stroke={TEAL} strokeWidth={2} dot={{ r: 3, fill: TEAL }} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Monthly Fuel Spend" empty={monthlyFuelCost.length === 0}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={monthlyFuelCost} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="month" tick={AXIS} />
            <YAxis tick={AXIS} />
            <Tooltip {...tooltipStyle} formatter={(v: number) => [`$${v.toFixed(2)}`, 'Fuel Cost']} />
            <Bar dataKey="value" fill={TEAL} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Cost Breakdown" empty={costBreakdown.length === 0}>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={costBreakdown}
              cx="50%"
              cy="45%"
              innerRadius={55}
              outerRadius={85}
              paddingAngle={3}
              dataKey="value"
            >
              {costBreakdown.map((_, i) => (
                <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip {...tooltipStyle} formatter={(v: number) => [`$${v.toFixed(2)}`, '']} />
            <Legend
              iconType="circle"
              iconSize={8}
              formatter={(value) => <span style={{ color: '#94a3b8', fontSize: 12 }}>{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Monthly Maintenance Cost" empty={monthlyMaintCost.length === 0}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={monthlyMaintCost} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="month" tick={AXIS} />
            <YAxis tick={AXIS} />
            <Tooltip {...tooltipStyle} formatter={(v: number) => [`$${v.toFixed(2)}`, 'Cost']} />
            <Bar dataKey="value" fill={AMBER} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Odometer History" empty={odometerData.length < 2}>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={odometerData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="date" tick={AXIS} />
            <YAxis tick={AXIS} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
            <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toLocaleString()} mi`, 'Odometer']} />
            <Line type="monotone" dataKey="mileage" stroke={INDIGO} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Cost per Mile" empty={costPerMileData.length < 2}>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={costPerMileData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="date" tick={AXIS} />
            <YAxis tick={AXIS} tickFormatter={(v) => `$${v.toFixed(2)}`} />
            <Tooltip {...tooltipStyle} formatter={(v: number) => [`$${v.toFixed(4)}/mi`, 'Cost per Mile']} />
            <Line type="monotone" dataKey="cpm" stroke={RED} strokeWidth={2} dot={{ r: 3, fill: RED }} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {isGasoline && (
        <ChartCard title="Octane Grade per Fill-up" empty={octaneData.length < 2}>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={octaneData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis dataKey="date" tick={AXIS} />
              <YAxis tick={AXIS} domain={[85, 'auto']} />
              <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v}`, 'Octane']} />
              <Line type="stepAfter" dataKey="octane" stroke={AMBER} strokeWidth={2} dot={{ r: 3, fill: AMBER }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      )}
    </div>
  );
}
