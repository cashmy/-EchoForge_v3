export const SettingsPage = () => (
  <div className="space-y-6">
    <header>
      <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
        Workspace Settings
      </p>
      <h1 className="text-2xl font-semibold text-[var(--color-text)]">
        Settings
      </h1>
      <p className="mt-2 text-sm text-[var(--color-text-muted)]">
        Theme, table density, and Whisper/transcript visibility will connect to
        EF-01 + MI99 surfaces later in M05. This placeholder page anchors the
        route and provides cards for future forms.
      </p>
    </header>
    <section className="grid gap-4 md:grid-cols-2">
      {["Theme", "Table Density", "Whisper"].map((card) => (
        <div
          key={card}
          className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm text-[var(--color-text)]"
        >
          <h2 className="text-base font-semibold text-[var(--color-text)]">
            {card}
          </h2>
          <p className="mt-2 text-[var(--color-text-muted)]">
            Configuration form placeholder. Hook into Zustand + backend when
            requirements land.
          </p>
        </div>
      ))}
    </section>
  </div>
);
