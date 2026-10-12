export function Lightbox({ src, alt = "", onClose }) {
  if (!src) return null;
  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        className="absolute right-4 top-4 rounded-full bg-white/10 px-3 py-1 text-sm text-white"
        onClick={onClose}
      >
        关闭
      </button>
      <img
        src={src}
        alt={alt}
        className="max-h-[90vh] max-w-[92vw] rounded-lg object-contain shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}
