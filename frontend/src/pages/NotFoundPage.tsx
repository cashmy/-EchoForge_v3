import { Link } from "react-router-dom";

export const NotFoundPage = () => (
  <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-8 py-16 text-center text-[var(--color-text)]">
    <p className="text-sm uppercase tracking-[0.4em] text-[var(--color-text-muted)]">
      404
    </p>
    <h1 className="text-3xl font-semibold text-[var(--color-text)]">
      Page not found
    </h1>
    <p className="max-w-md text-sm text-[var(--color-text-muted)]">
      The requested view is not part of the M05 routing scaffold yet. Use the
      link below to return to the dashboard.
    </p>
    <Link
      to="/"
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-2 text-sm font-semibold text-[var(--color-text)]"
    >
      Back to Dashboard
    </Link>
  </div>
);
