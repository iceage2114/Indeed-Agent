// ConfirmModal.jsx — Centered confirmation dialog with Cancel and Confirm buttons

export default function ConfirmModal({ message, confirmLabel = "Confirm", confirmClass = "bg-blue-600 hover:bg-blue-700", onConfirm, onCancel }) {
  if (!message) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full mx-4 flex flex-col gap-5"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="text-gray-800 text-base font-medium leading-relaxed text-center">
          {message}
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={onCancel}
            className="flex-1 py-2 rounded-lg border border-gray-300 text-gray-700 text-sm font-semibold hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`flex-1 py-2 rounded-lg text-white text-sm font-semibold transition-colors ${confirmClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
