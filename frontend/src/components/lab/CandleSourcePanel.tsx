import type { CandleImportRequest, CandleImportResult, CandleSourceStatus } from "../../api/types";

export function CandleSourcePanel({
  source,
  pending,
  errorMessage,
  importResult,
  onImportCandles,
}: {
  readonly source: CandleSourceStatus | null;
  readonly pending: boolean;
  readonly errorMessage: string | null;
  readonly importResult: CandleImportResult | null;
  readonly onImportCandles: (payload: CandleImportRequest) => void | Promise<void>;
}) {
  const facts = candleSourceFacts(source);
  const latestPagePayload = {
    instrument: facts.instrument,
    count: facts.importPolicy.pageSize,
  };
  return (
    <section className="lab-panel" aria-label="Candle source">
      <div className="lab-panel__header">
        <h2>Candle Dataset</h2>
        <div className="lab-panel__actions">
          <button
            type="button"
            className="lab-button lab-button--quiet"
            disabled={pending || !facts.oandaHistoricalImportConfigured}
            onClick={() => void onImportCandles(latestPagePayload)}
          >
            Refresh latest {facts.importPolicy.pageSize.toLocaleString()} M1
          </button>
          <button
            type="button"
            className="lab-button"
            disabled={pending || !facts.oandaHistoricalImportConfigured}
            onClick={() =>
              void onImportCandles({
                instrument: facts.instrument,
                count: facts.importPolicy.defaultCount,
                from: backfillStart(facts.importPolicy.defaultCount),
              })
            }
          >
            Backfill {importDaysLabel(facts.importPolicy.defaultCount)}
          </button>
        </div>
      </div>
      <p className="lab-source-note">{facts.guidance}</p>
      <ul className="fact-list">
        {facts.rows.map((row) => (
          <li key={row.label}>
            {row.label}: {row.value}
          </li>
        ))}
      </ul>
      {errorMessage ? (
        <p className="lab-live-status" aria-live="polite">
          {errorMessage}
        </p>
      ) : null}
      {importResult ? <CandleImportNotice importResult={importResult} /> : null}
    </section>
  );
}

function CandleImportNotice({ importResult }: { readonly importResult: CandleImportResult }) {
  return (
    <p className="lab-live-status" aria-live="polite">
      Upserted {importResult.imported_count} of {importResult.requested_count} requested candles
      from {importResult.from ?? "latest page"}. Coverage {importResult.coverage.from ?? "none"} to{" "}
      {importResult.coverage.to ?? "none"}.
    </p>
  );
}

function candleSourceFacts(source: CandleSourceStatus | null) {
  if (source === null) {
    return {
      instrument: "EUR_USD",
      oandaHistoricalImportConfigured: false,
      guidance:
        "Candles come from OANDA practice REST into the persisted M1 midpoint candle store. Configure OANDA_ACCOUNT_ID and OANDA_API_TOKEN before importing.",
      importPolicy: { pageSize: 5000, defaultCount: 43200 },
      rows: candleSourceRows({
        source: "persisted_candles",
        instrument: "EUR_USD",
        granularity: "M1",
        priceComponent: "midpoint",
        candleCount: 0,
        from: "none",
        to: "none",
        configured: false,
        pageSize: 5000,
        defaultCount: 43200,
        upsertKey: "instrument+timestamp",
        replacesExisting: false,
      }),
    };
  }

  const coverage = source.coverage;
  const importPolicy = source.historical_import;
  return {
    instrument: source.instrument,
    oandaHistoricalImportConfigured: source.oanda_historical_import_configured,
    importPolicy: {
      pageSize: importPolicy.page_size,
      defaultCount: importPolicy.default_count,
    },
    guidance: candleSourceGuidance(source),
    rows: candleSourceRows({
      source: source.primary_source,
      instrument: source.instrument,
      granularity: source.granularity,
      priceComponent: source.price_component,
      candleCount: coverage.candle_count,
      from: coverage.from ?? "none",
      to: coverage.to ?? "none",
      configured: source.oanda_historical_import_configured,
      pageSize: importPolicy.page_size,
      defaultCount: importPolicy.default_count,
      upsertKey: importPolicy.upsert_key,
      replacesExisting: importPolicy.replaces_existing,
    }),
  };
}

function candleSourceRows(input: {
  readonly source: string;
  readonly instrument: string;
  readonly granularity: string;
  readonly priceComponent: string;
  readonly candleCount: number;
  readonly from: string;
  readonly to: string;
  readonly configured: boolean;
  readonly pageSize: number;
  readonly defaultCount: number;
  readonly upsertKey: string;
  readonly replacesExisting: boolean;
}) {
  return [
    { label: "path", value: "OANDA practice REST -> persisted candles -> Lab optimizer" },
    { label: "source", value: input.source },
    { label: "write policy", value: input.replacesExisting ? "replace" : "upsert" },
    { label: "upsert key", value: input.upsertKey },
    { label: "method", value: "OANDA historical import" },
    { label: "instrument", value: input.instrument },
    { label: "granularity", value: input.granularity },
    { label: "price", value: input.priceComponent },
    { label: "candles", value: String(input.candleCount) },
    { label: "from", value: input.from },
    { label: "to", value: input.to },
    { label: "latest-page request", value: `${input.pageSize.toLocaleString()} M1 candles` },
    { label: "backfill request", value: `${input.defaultCount.toLocaleString()} M1 candles` },
    { label: "configured", value: String(input.configured) },
  ];
}

function candleSourceGuidance(source: CandleSourceStatus) {
  if (!source.oanda_historical_import_configured) {
    return "OANDA credentials are missing. Import would load practice M1 midpoint candles into Harbor's database for Lab studies.";
  }
  if (source.coverage.candle_count === 0) {
    return "No persisted M1 midpoint candles are available for Lab tuning.";
  }
  return "Lab tuning reads the persisted M1 midpoint candle dataset shown below.";
}

function backfillStart(count: number): string {
  return new Date(Date.now() - count * 60_000).toISOString();
}

function importDaysLabel(count: number): string {
  const days = Math.round(count / 1440);
  return `${days} days`;
}
