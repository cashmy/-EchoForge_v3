import { Link, isRouteErrorResponse, useRouteError } from "react-router-dom";

const getErrorMessage = (error: unknown) => {
  if (isRouteErrorResponse(error)) {
    return {
      title: `HTTP ${error.status}`,
      detail: error.statusText || "Request failed",
    };
  }
  if (error instanceof Error) {
    return { title: "Application Error", detail: error.message };
  }
  return { title: "Unexpected Error", detail: "Something went wrong." };
};

export const RouteErrorPage = () => {
  const error = useRouteError();
  const message = getErrorMessage(error);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)] px-6 py-12 text-[var(--color-text)]">
      <div className="w-full max-w-xl space-y-6 rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center shadow-[0_30px_80px_rgba(2,6,23,0.35)]">
        <p className="text-xs uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
          Application Error
        </p>
        <h1 className="text-2xl font-semibold">{message.title}</h1>
        <p className="text-sm text-[var(--color-text-muted)]">
          {message.detail}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3 pt-4 text-xs font-semibold uppercase tracking-[0.3em]">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-full border border-[var(--color-border)] px-5 py-2"
          >
            Reload
          </button>
          <Link
            to="/"
            className="rounded-full border border-[var(--color-accent)] bg-[var(--color-accent)]/10 px-5 py-2 text-[var(--color-accent)]"
          >
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
};
