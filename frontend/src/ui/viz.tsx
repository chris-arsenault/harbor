interface Extent {
  readonly min: number;
  readonly max: number;
}

function extent(values: number[], pad = 0.04): Extent {
  if (values.length === 0) {
    return { min: 0, max: 1 };
  }
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const span = (max - min) * pad;
  return { min: min - span, max: max + span };
}

function scale(value: number, domain: Extent, size: number, invert = false): number {
  const ratio = (value - domain.min) / (domain.max - domain.min);
  return invert ? size - ratio * size : ratio * size;
}

/* ---------------------------------------------------------------- Sparkline */
export function Sparkline({
  values,
  width = 88,
  height = 26,
}: {
  readonly values: number[];
  readonly width?: number;
  readonly height?: number;
}) {
  if (values.length < 2) {
    return <svg className="spark" width={width} height={height} aria-hidden="true" />;
  }
  const yd = extent(values);
  const step = width / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(1)},${scale(v, yd, height, true).toFixed(1)}`)
    .join(" ");
  return (
    <svg className="spark" width={width} height={height} aria-hidden="true">
      <polyline className="spark-line" points={points} />
    </svg>
  );
}

/* ---------------------------------------------------------------- Area/line */
export interface SeriesPoint {
  readonly v: number;
}

export function AreaCurve({
  points,
  ariaLabel,
  dataPoints,
  height = 170,
  width = 560,
  tone = "beam",
}: {
  readonly points: SeriesPoint[];
  readonly ariaLabel: string;
  readonly dataPoints?: string;
  readonly height?: number;
  readonly width?: number;
  readonly tone?: "beam" | "up" | "down";
}) {
  if (points.length < 2) {
    return <VizEmpty ariaLabel={ariaLabel} dataPoints={dataPoints} height={height} width={width} />;
  }
  const yd = extent(points.map((p) => p.v));
  const step = width / (points.length - 1);
  const coords = points.map((p, i) => ({
    x: i * step,
    y: scale(p.v, yd, height, true),
  }));
  const line = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;
  const lineClass = tone === "beam" ? "viz-line" : `viz-line viz-line--${tone}`;
  return (
    <svg
      className="viz"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel}
      data-points={dataPoints}
      preserveAspectRatio="none"
    >
      <polygon className="viz-area" points={area} />
      <polyline className={lineClass} points={line} />
    </svg>
  );
}

/* ---------------------------------------------------------------- Scatter */
export interface ScatterPoint {
  readonly x: number;
  readonly y: number;
  readonly kind: "default" | "paper" | "promoted" | "pruned";
}

export function Scatter({
  points,
  ariaLabel,
  dataPoints,
  size = 220,
}: {
  readonly points: ScatterPoint[];
  readonly ariaLabel: string;
  readonly dataPoints?: string;
  readonly size?: number;
}) {
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const all = [...xs, ...ys];
  const dom = extent(all.length > 0 ? all : [0, 1]);
  const pad = 22;
  const inner = size - pad * 2;
  const place = (v: number, invert = false) => pad + scale(v, dom, inner, invert);
  return (
    <svg
      className="viz"
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={ariaLabel}
      data-points={dataPoints}
    >
      <line className="viz-axis" x1={pad} y1={pad} x2={pad} y2={size - pad} />
      <line className="viz-axis" x1={pad} y1={size - pad} x2={size - pad} y2={size - pad} />
      <line className="viz-diag" x1={pad} y1={size - pad} x2={size - pad} y2={pad} />
      {points.map((p, i) => (
        <circle
          key={i}
          className={`viz-dot viz-dot--${p.kind}`}
          cx={place(p.x)}
          cy={place(p.y, true)}
          r={p.kind === "pruned" ? 2.6 : 3.6}
        />
      ))}
      <text className="viz-axis-label" x={pad} y={size - 6}>
        in-sample →
      </text>
      <text className="viz-axis-label" x={6} y={pad - 8} transform={`rotate(-90 6 ${pad - 8})`}>
        out-of-sample →
      </text>
    </svg>
  );
}

/* ---------------------------------------------------------------- Bar list */
export interface BarDatum {
  readonly label: string;
  readonly value: number;
  readonly display: string;
}

export function BarList({
  data,
  ariaLabel,
}: {
  readonly data: BarDatum[];
  readonly ariaLabel: string;
}) {
  const peak = Math.max(1, ...data.map((d) => Math.abs(d.value)));
  const rowH = 22;
  const labelW = 116;
  const barW = 240;
  const width = labelW + barW + 60;
  const height = Math.max(rowH, data.length * rowH);
  return (
    <svg
      className="viz"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel}
      preserveAspectRatio="xMinYMin meet"
    >
      {data.map((d, i) => {
        const w = (Math.abs(d.value) / peak) * barW;
        const y = i * rowH + 4;
        return (
          <g key={d.label}>
            <text className="viz-axis-label" x={0} y={y + 11}>
              {d.label}
            </text>
            <rect
              className={d.value < 0 ? "viz-bar viz-bar--neg" : "viz-bar"}
              x={labelW}
              y={y}
              width={Math.max(1, w)}
              height={rowH - 8}
              rx={2}
            />
            <text className="viz-axis-label" x={labelW + Math.max(1, w) + 5} y={y + 11}>
              {d.display}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* ---------------------------------------------------------------- Gauge */
export function ScoreGauge({
  score,
  caption,
  size = 116,
}: {
  readonly score: number;
  readonly caption: string;
  readonly size?: number;
}) {
  const clamped = Math.max(0, Math.min(100, score));
  const r = size / 2 - 9;
  const circ = 2 * Math.PI * r;
  const dash = (clamped / 100) * circ;
  return (
    <svg
      className="gauge__dial"
      width={size}
      height={size}
      role="img"
      aria-label={`${caption} ${Math.round(clamped)}`}
    >
      <circle className="gauge__ring-bg" cx={size / 2} cy={size / 2} r={r} />
      <circle
        className="gauge__ring"
        cx={size / 2}
        cy={size / 2}
        r={r}
        strokeDasharray={`${dash.toFixed(1)} ${circ.toFixed(1)}`}
      />
      <text className="gauge__num" x={size / 2} y={size / 2 - 2}>
        {Math.round(clamped)}
      </text>
      <text className="gauge__cap" x={size / 2} y={size / 2 + 18}>
        {caption}
      </text>
    </svg>
  );
}

function VizEmpty({
  ariaLabel,
  dataPoints,
  height,
  width,
}: {
  readonly ariaLabel: string;
  readonly dataPoints?: string;
  readonly height: number;
  readonly width: number;
}) {
  return (
    <svg
      className="viz"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={ariaLabel}
      data-points={dataPoints ?? ""}
      preserveAspectRatio="none"
    >
      <line className="viz-grid" x1={0} y1={height / 2} x2={width} y2={height / 2} />
    </svg>
  );
}
