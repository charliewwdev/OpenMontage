import { ModalOverlay } from "./ModalPortal";

export function Lightbox({ src, alt = "", onClose }) {
  if (!src) return null;
  return (
    <ModalOverlay onClose={onClose} className="bg-black/80" zClass="z-[200]" role="dialog">
      <div className="relative my-auto w-fit max-w-[92vw]" onMouseDown={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="absolute right-2 top-2 z-10 rounded-full bg-black/65 px-3 py-1 text-sm text-white hover:bg-black/80"
          onClick={onClose}
        >
          关闭
        </button>
        <img
          src={src}
          alt={alt}
          className="block max-h-[min(90dvh,90vh)] max-w-[92vw] rounded-lg object-contain shadow-2xl"
        />
      </div>
    </ModalOverlay>
  );
}
