import type { ReactNode } from 'react';

export function ConfirmDialog({
  open, title, body, confirmLabel = 'Confirm', onConfirm, onCancel,
}: {
  open: boolean;
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
         role="dialog" aria-modal="true">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-2">{title}</h3>
        {body && <div className="text-slate-300 mb-4">{body}</div>}
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-3 py-1.5 rounded bg-slate-700">
            Cancel
          </button>
          <button onClick={onConfirm} className="px-3 py-1.5 rounded bg-red-600 text-white">
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
