import type { CandleImportRequest, CandleImportResult, CandleSourceStatus } from "../../api/types";
import { fmtDate, fmtInt } from "../../ui/format";
import { Field, Notice, Panel, StatTile } from "../../ui/primitives";

const DEFAULT_PAGE = 5000;
const DEFAULT_BACKFILL = 259_200;

function backfillStart(count: number): string {
  return new Date(Date.now() - count * 60_000).toISOString();
}

function importNotice(result: CandleImportResult): string {
  const target =
    result.instrument === "research_universe"
      ? `${result.results?.length ?? 0} instruments`
      : result.instrument;
  return `Imported ${fmtInt(result.imported_count)} / ${fmtInt(result.requested_count)} candles for ${target}.`;
}

interface ImportPlan {
  readonly page: number;
  readonly backfill: number;
  readonly universe: string[];
  readonly disabled: boolean;
  readonly latest: CandleImportRequest;
  readonly fill: CandleImportRequest;
  readonly fillUniverse: CandleImportRequest;
}

function universeFor(source: CandleSourceStatus | null, instrument: string): string[] {
  return source?.research_instruments?.length ? source.research_instruments : [instrument];
}

function importDisabled(source: CandleSourceStatus | null, pending: boolean): boolean {
  return pending || !(source?.oanda_historical_import_configured ?? false);
}

function importPlan(
  source: CandleSourceStatus | null,
  instrument: string,
  pending: boolean
): ImportPlan {
  const policy = source?.historical_import;
  const page = policy?.page_size ?? DEFAULT_PAGE;
  const backfill = Math.max(policy?.default_count ?? DEFAULT_BACKFILL, DEFAULT_BACKFILL);
  const universe = universeFor(source, instrument);
  const from = backfillStart(backfill);
  return {
    page,
    backfill,
    universe,
    disabled: importDisabled(source, pending),
    latest: { instrument, count: page },
    fill: { instrument, count: backfill, from },
    fillUniverse: { instrument: "research_universe", instruments: universe, count: backfill, from },
  };
}

function CoverageTiles({ source }: { readonly source: CandleSourceStatus | null }) {
  const coverage = source?.coverage;
  return (
    <div className="tiles tiles--tight">
      <StatTile label="Candles" value={fmtInt(coverage?.candle_count ?? 0)} tone="beam" />
      <StatTile label="From" value={fmtDate(coverage?.from)} />
      <StatTile label="To" value={fmtDate(coverage?.to)} />
      <StatTile
        label="Write policy"
        value={source?.historical_import.upsert_key ? "upsert" : "—"}
      />
    </div>
  );
}

function ImportActions({
  plan,
  onImportCandles,
}: {
  readonly plan: ImportPlan;
  readonly onImportCandles: (payload: CandleImportRequest) => void | Promise<void>;
}) {
  return (
    <div className="row">
      <button
        type="button"
        className="btn btn--ghost"
        disabled={plan.disabled}
        onClick={() => void onImportCandles(plan.latest)}
      >
        Refresh latest {fmtInt(plan.page)} M1
      </button>
      <button
        type="button"
        className="btn"
        disabled={plan.disabled}
        onClick={() => void onImportCandles(plan.fill)}
      >
        Backfill history
      </button>
      <button
        type="button"
        className="btn btn--ghost"
        disabled={plan.disabled}
        onClick={() => void onImportCandles(plan.fillUniverse)}
      >
        Fill research universe
      </button>
    </div>
  );
}

export function CandleSource({
  source,
  selectedInstrument,
  pending,
  errorMessage,
  importResult,
  onInstrumentChange,
  onImportCandles,
}: {
  readonly source: CandleSourceStatus | null;
  readonly selectedInstrument: string;
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly importResult: CandleImportResult | null;
  readonly onInstrumentChange: (instrument: string) => void;
  readonly onImportCandles: (payload: CandleImportRequest) => void | Promise<void>;
}) {
  const plan = importPlan(source, selectedInstrument, pending);
  const note = source ? `${source.granularity} ${source.price_component}` : "loading";
  return (
    <Panel
      title="Candle source"
      note={note}
      label="Candle source"
      actions={
        <Field label="Instrument">
          <select
            className="select"
            value={selectedInstrument}
            onChange={(event) => onInstrumentChange(event.target.value)}
          >
            {plan.universe.map((symbol) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </Field>
      }
    >
      <CoverageTiles source={source} />
      <ImportActions plan={plan} onImportCandles={onImportCandles} />
      {errorMessage ? <Notice tone="error">{errorMessage}</Notice> : null}
      {importResult ? <Notice tone="ok">{importNotice(importResult)}</Notice> : null}
    </Panel>
  );
}
