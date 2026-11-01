import { t } from '../lib/i18n';
import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
export function Modal({ title, children, onClose, className }: {
    title: string;
    children: ReactNode;
    onClose: () => void;
    className?: string;
}) {
    const ref = useRef<HTMLDialogElement>(null);
    useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close(); }, []);
    return <dialog className={className} ref={ref} onCancel={onClose} onClick={e => {
            if (e.target === e.currentTarget)
                onClose();
        }}><header className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label={t("Close")}><X size={20}/></button></header>{children}</dialog>;
}
