import { ReactNode } from "react";
import { X } from "lucide-react";

interface ModalProps {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
}

export const Modal = ({
  open,
  title,
  children,
  onClose,
  footer,
}: ModalProps) => {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div
        className="absolute inset-0 bg-black/50"
        role="presentation"
        onClick={onClose}
      />
      <div className="relative z-10 w-full max-w-lg rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl">
        <header className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-3">
          <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-[var(--color-text-muted)]">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-1"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close modal</span>
          </button>
        </header>
        <div className="px-5 py-4 text-sm text-[var(--color-text)]">
          {children}
        </div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-3 border-t border-[var(--color-border)] px-5 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
