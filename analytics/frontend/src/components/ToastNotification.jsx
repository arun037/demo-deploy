import React, { useEffect, useState } from 'react';
import { CheckCircle, AlertCircle, X, Info } from 'lucide-react';

const ToastNotification = ({ message, type = 'info', onClose, duration = 4000 }) => {
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        // Small delay to allow enter animation
        const showTimer = setTimeout(() => setIsVisible(true), 10);

        // Auto-dismiss timer
        const dismissTimer = setTimeout(() => {
            setIsVisible(false);
            // Wait for exit animation before calling onClose
            setTimeout(onClose, 300);
        }, duration);

        return () => {
            clearTimeout(showTimer);
            clearTimeout(dismissTimer);
        };
    }, [duration, onClose]);

    const handleClose = () => {
        setIsVisible(false);
        setTimeout(onClose, 300);
    };

    const styles = {
        success: 'bg-brand-green/10 border-brand-green/30 text-brand-green',
        error: 'bg-red-50 border-red-200 text-red-800',
        info: 'bg-brand-teal/10 border-brand-teal/30 text-brand-teal'
    };

    const icons = {
        success: <CheckCircle className="w-5 h-5 text-brand-green" />,
        error: <AlertCircle className="w-5 h-5 text-red-500" />,
        info: <Info className="w-5 h-5 text-brand-teal" />
    };

    return (
        <div
            className={`fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg transition-all duration-300 transform ${isVisible ? 'translate-y-0 opacity-100' : '-translate-y-4 opacity-0'
                } ${styles[type] || styles.info}`}
            role="alert"
        >
            <div className="flex-shrink-0">
                {icons[type] || icons.info}
            </div>
            <p className="text-sm font-medium">{message}</p>
            <button
                onClick={handleClose}
                className="p-1 rounded-full hover:bg-black/5 transition-colors ml-2"
                aria-label="Close notification"
            >
                <X className="w-4 h-4 opacity-60" />
            </button>
        </div>
    );
};

export default ToastNotification;
