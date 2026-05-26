import { useToastStore } from '../stores/toastStore';

export default function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl border text-sm font-medium max-w-sm ${
            toast.type === 'success'
              ? 'bg-green-900/95 border-green-700 text-green-100'
              : toast.type === 'error'
              ? 'bg-red-900/95 border-red-700 text-red-100'
              : 'bg-teal-900/95 border-teal-700 text-teal-100'
          }`}
        >
          <span className="flex-1">{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            className="opacity-60 hover:opacity-100 text-xl leading-none ml-1 flex-shrink-0"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
