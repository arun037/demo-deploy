import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { config } from '../config.js';
import { MessageSquare, Clock, Trash2, Search, AlertCircle, RefreshCw, Edit2, Check, X, CheckSquare, Square } from 'lucide-react';
import { formatTimeAgo } from '../utils/dateFormatters.js';

function ChatHistoryPage() {
    const [sessions, setSessions] = useState([]);
    const [filteredSessions, setFilteredSessions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [error, setError] = useState(null);
    const [sessionToDelete, setSessionToDelete] = useState(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [notification, setNotification] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const navigate = useNavigate();
    const observerTarget = useRef(null);
    const [editingSessionId, setEditingSessionId] = useState(null);
    const [editingTitle, setEditingTitle] = useState('');

    // Multi-select state
    const [selectMode, setSelectMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState(new Set());
    const [showBulkDeleteConfirm, setShowBulkDeleteConfirm] = useState(false);
    const [bulkDeleting, setBulkDeleting] = useState(false);

    // Initial load
    useEffect(() => {
        loadSessions(1);
    }, []);

    // Filter sessions when search term changes
    useEffect(() => {
        if (searchTerm.trim() === '') {
            setFilteredSessions(sessions);
        } else {
            const filtered = sessions.filter(session =>
                session.title.toLowerCase().includes(searchTerm.toLowerCase())
            );
            setFilteredSessions(filtered);
        }
    }, [searchTerm, sessions]);

    // Infinite scroll observer
    useEffect(() => {
        if (!hasMore || loadingMore || searchTerm) return;

        const observer = new IntersectionObserver(
            entries => {
                if (entries[0].isIntersecting) {
                    loadMoreSessions();
                }
            },
            { threshold: 0.1 }
        );

        if (observerTarget.current) {
            observer.observe(observerTarget.current);
        }

        return () => observer.disconnect();
    }, [hasMore, loadingMore, page, searchTerm]);

    const loadSessions = async (pageNum) => {
        try {
            setError(null);
            const res = await fetch(`${config.API.SESSIONS_ENDPOINT}?page=${pageNum}&limit=50`);

            if (!res.ok) {
                throw new Error(`Failed to load sessions (${res.status})`);
            }

            const data = await res.json();

            if (data.success) {
                setSessions(data.sessions);
                setFilteredSessions(data.sessions);
                setHasMore(data.has_more);
                setPage(pageNum);
            } else {
                throw new Error(data.message || 'Failed to load sessions');
            }
        } catch (err) {
            console.error('Failed to load sessions:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const loadMoreSessions = async () => {
        if (loadingMore || !hasMore) return;

        setLoadingMore(true);
        try {
            const nextPage = page + 1;
            const res = await fetch(`${config.API.SESSIONS_ENDPOINT}?page=${nextPage}&limit=50`);

            if (!res.ok) {
                throw new Error(`Failed to load more sessions (${res.status})`);
            }

            const data = await res.json();

            if (data.success) {
                setSessions(prev => [...prev, ...data.sessions]);
                setHasMore(data.has_more);
                setPage(nextPage);
            }
        } catch (err) {
            console.error('Failed to load more sessions:', err);
        } finally {
            setLoadingMore(false);
        }
    };

    const handleRetry = () => {
        setLoading(true);
        setError(null);
        loadSessions(1);
    };

    const openSession = (sessionId) => {
        if (selectMode) return; // don't open when in select mode
        navigate('/chat', { state: { sessionId } });
    };

    // ── Single delete ─────────────────────────────────────────────────────────
    const handleDeleteClick = (e, session) => {
        e.stopPropagation();
        setSessionToDelete(session);
        setShowDeleteConfirm(true);
    };

    const confirmDelete = async () => {
        if (!sessionToDelete) return;

        setDeleting(true);
        try {
            const res = await fetch(`${config.API.SESSIONS_ENDPOINT}/${sessionToDelete.session_id}`, {
                method: 'DELETE'
            });

            if (res.ok) {
                setSessions(prev => prev.filter(s => s.session_id !== sessionToDelete.session_id));
                setNotification({ type: 'success', message: 'Chat deleted successfully' });
                setTimeout(() => setNotification(null), 3000);
            } else {
                throw new Error('Failed to delete session');
            }
        } catch (error) {
            console.error('Failed to delete session:', error);
            setNotification({ type: 'error', message: 'Failed to delete chat' });
            setTimeout(() => setNotification(null), 3000);
        } finally {
            setDeleting(false);
            setShowDeleteConfirm(false);
            setSessionToDelete(null);
        }
    };

    const cancelDelete = () => {
        setShowDeleteConfirm(false);
        setSessionToDelete(null);
    };

    // ── Edit title ────────────────────────────────────────────────────────────
    const handleEditClick = (e, session) => {
        e.stopPropagation();
        setEditingSessionId(session.session_id);
        setEditingTitle(session.title);
    };

    const handleSaveEdit = async (e, sessionId) => {
        e.stopPropagation();

        const trimmedTitle = editingTitle.trim();
        if (!trimmedTitle) {
            setNotification({ type: 'error', message: 'Title cannot be empty' });
            setTimeout(() => setNotification(null), 3000);
            return;
        }

        try {
            const res = await fetch(`${config.API.SESSIONS_ENDPOINT}/${sessionId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: trimmedTitle })
            });

            if (res.ok) {
                setSessions(prev => prev.map(s =>
                    s.session_id === sessionId ? { ...s, title: trimmedTitle } : s
                ));
                setNotification({ type: 'success', message: 'Title updated successfully' });
                setTimeout(() => setNotification(null), 3000);
            } else {
                throw new Error('Failed to update title');
            }
        } catch (error) {
            console.error('Failed to update session title:', error);
            setNotification({ type: 'error', message: 'Failed to update title' });
            setTimeout(() => setNotification(null), 3000);
        } finally {
            setEditingSessionId(null);
            setEditingTitle('');
        }
    };

    const handleCancelEdit = (e) => {
        e.stopPropagation();
        setEditingSessionId(null);
        setEditingTitle('');
    };

    // ── Multi-select helpers ───────────────────────────────────────────────────
    const toggleSelectMode = () => {
        setSelectMode(prev => !prev);
        setSelectedIds(new Set());
    };

    const toggleSelect = (e, sessionId) => {
        e.stopPropagation();
        setSelectedIds(prev => {
            const next = new Set(prev);
            next.has(sessionId) ? next.delete(sessionId) : next.add(sessionId);
            return next;
        });
    };

    const isAllSelected = filteredSessions.length > 0 && filteredSessions.every(s => selectedIds.has(s.session_id));

    const toggleSelectAll = () => {
        if (isAllSelected) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredSessions.map(s => s.session_id)));
        }
    };

    // ── Bulk delete ───────────────────────────────────────────────────────────
    const handleBulkDeleteClick = () => {
        if (selectedIds.size === 0) return;
        setShowBulkDeleteConfirm(true);
    };

    const confirmBulkDelete = async () => {
        setBulkDeleting(true);
        const ids = Array.from(selectedIds);
        let successCount = 0;

        await Promise.all(
            ids.map(async (id) => {
                try {
                    const res = await fetch(`${config.API.SESSIONS_ENDPOINT}/${id}`, { method: 'DELETE' });
                    if (res.ok) successCount++;
                } catch (_) {}
            })
        );

        setSessions(prev => prev.filter(s => !selectedIds.has(s.session_id)));
        setSelectedIds(new Set());
        setSelectMode(false);
        setShowBulkDeleteConfirm(false);
        setBulkDeleting(false);
        setNotification({
            type: 'success',
            message: `${successCount} chat${successCount !== 1 ? 's' : ''} deleted`
        });
        setTimeout(() => setNotification(null), 3000);
    };

    // ── Render ────────────────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-brand-navy mx-auto mb-4"></div>
                    <p className="text-sm text-slate-600">Loading chat history...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center max-w-md mx-4">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-100 flex items-center justify-center">
                        <AlertCircle size={32} className="text-red-600" />
                    </div>
                    <h2 className="text-lg font-semibold text-slate-800 mb-2">Failed to Load History</h2>
                    <p className="text-sm text-slate-600 mb-4">{error}</p>
                    <button
                        onClick={handleRetry}
                        className="inline-flex items-center gap-2 px-4 py-2 bg-brand-navy text-white rounded-lg hover:bg-opacity-90 transition-colors"
                    >
                        <RefreshCw size={16} />
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-gradient-to-br from-slate-50 to-blue-50">

            {/* Notification Toast */}
            {notification && (
                <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg ${notification.type === 'success'
                    ? 'bg-green-500 text-white'
                    : 'bg-red-500 text-white'
                    }`}>
                    {notification.message}
                </div>
            )}

            {/* Single Delete Confirmation */}
            {showDeleteConfirm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg shadow-xl p-6 max-w-md mx-4">
                        <h3 className="text-lg font-semibold text-slate-800 mb-2">Delete Chat?</h3>
                        <p className="text-sm text-slate-600 mb-4">
                            Are you sure you want to delete "{sessionToDelete?.title}"? This action cannot be undone.
                        </p>
                        <div className="flex gap-3 justify-end">
                            <button onClick={cancelDelete} disabled={deleting}
                                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50">
                                Cancel
                            </button>
                            <button onClick={confirmDelete} disabled={deleting}
                                className="px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-colors disabled:opacity-50 flex items-center gap-2">
                                {deleting ? 'Deleting...' : 'Delete'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Bulk Delete Confirmation */}
            {showBulkDeleteConfirm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg shadow-xl p-6 max-w-md mx-4">
                        <h3 className="text-lg font-semibold text-slate-800 mb-2">Delete {selectedIds.size} Chat{selectedIds.size !== 1 ? 's' : ''}?</h3>
                        <p className="text-sm text-slate-600 mb-4">
                            This will permanently delete {selectedIds.size} selected chat{selectedIds.size !== 1 ? 's' : ''}. This action cannot be undone.
                        </p>
                        <div className="flex gap-3 justify-end">
                            <button onClick={() => setShowBulkDeleteConfirm(false)} disabled={bulkDeleting}
                                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50">
                                Cancel
                            </button>
                            <button onClick={confirmBulkDelete} disabled={bulkDeleting}
                                className="px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-colors disabled:opacity-50 flex items-center gap-2">
                                {bulkDeleting ? 'Deleting...' : `Delete ${selectedIds.size}`}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="p-4 flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-bold text-slate-800 mb-1">Chat History</h1>
                    <p className="text-sm text-slate-600">View and resume your previous conversations</p>
                </div>
                <button
                    onClick={toggleSelectMode}
                    className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${selectMode
                        ? 'bg-brand-navy text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
                >
                    {selectMode ? 'Cancel' : 'Select'}
                </button>
            </div>

            {/* Search Bar */}
            <div className="px-4 pb-4">
                <div className="relative">
                    <Search size={18} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
                    <input
                        type="text"
                        placeholder="Search chat history..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-navy focus:border-transparent"
                    />
                </div>
            </div>

            {/* Select-all bar (shown only in select mode) */}
            {selectMode && filteredSessions.length > 0 && (
                <div className="px-4 pb-2 flex items-center gap-2">
                    <button
                        onClick={toggleSelectAll}
                        className="flex items-center gap-2 text-sm text-slate-600 hover:text-brand-navy transition-colors"
                    >
                        {isAllSelected
                            ? <CheckSquare size={16} className="text-brand-navy" />
                            : <Square size={16} />}
                        {isAllSelected ? 'Deselect all' : 'Select all'}
                    </button>
                    {selectedIds.size > 0 && (
                        <span className="text-xs text-slate-400 ml-1">{selectedIds.size} selected</span>
                    )}
                </div>
            )}

            {/* Sessions List */}
            <div className="flex-1 overflow-y-auto px-4 pb-24 pr-2 scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
                {filteredSessions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center">
                        <MessageSquare size={48} className="text-slate-300 mb-3" />
                        <h2 className="text-lg font-semibold text-slate-700 mb-1">
                            {searchTerm ? 'No matching chats found' : 'No chat history yet'}
                        </h2>
                        <p className="text-sm text-slate-500">
                            {searchTerm ? 'Try a different search term' : 'Start a conversation to see it here'}
                        </p>
                    </div>
                ) : (
                    <div className="grid gap-2 max-w-4xl mx-auto">
                        {filteredSessions.map((session) => {
                            const isSelected = selectedIds.has(session.session_id);
                            return (
                                <div
                                    key={session.session_id}
                                    onClick={() => selectMode ? toggleSelect(null, session.session_id) : openSession(session.session_id)}
                                    className={`bg-white rounded-lg shadow-sm border px-3 py-2.5 transition-all cursor-pointer group
                                        ${isSelected
                                            ? 'border-brand-navy bg-blue-50'
                                            : 'border-slate-200 hover:shadow-md hover:border-brand-navy/30'}`}
                                >
                                    <div className="flex items-center justify-between">

                                        {/* Checkbox (select mode only) */}
                                        {selectMode && (
                                            <button
                                                onClick={(e) => toggleSelect(e, session.session_id)}
                                                className="mr-3 flex-shrink-0 text-brand-navy"
                                            >
                                                {isSelected
                                                    ? <CheckSquare size={18} className="text-brand-navy" />
                                                    : <Square size={18} className="text-slate-300" />}
                                            </button>
                                        )}

                                        <div className="flex-1 min-w-0 pr-2">
                                            {editingSessionId === session.session_id ? (
                                                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                                                    <input
                                                        type="text"
                                                        value={editingTitle}
                                                        onChange={(e) => setEditingTitle(e.target.value)}
                                                        onKeyDown={(e) => {
                                                            if (e.key === 'Enter') handleSaveEdit(e, session.session_id);
                                                            if (e.key === 'Escape') handleCancelEdit(e);
                                                        }}
                                                        className="flex-1 text-sm font-medium text-slate-700 px-2 py-1 border border-brand-navy/30 rounded focus:outline-none focus:ring-2 focus:ring-brand-navy"
                                                        autoFocus
                                                    />
                                                    <button onClick={(e) => handleSaveEdit(e, session.session_id)}
                                                        className="p-1 text-green-600 hover:bg-green-50 rounded transition-colors" title="Save">
                                                        <Check size={16} />
                                                    </button>
                                                    <button onClick={handleCancelEdit}
                                                        className="p-1 text-red-600 hover:bg-red-50 rounded transition-colors" title="Cancel">
                                                        <X size={16} />
                                                    </button>
                                                </div>
                                            ) : (
                                                <>
                                                    <h3 className="text-sm font-medium text-slate-700 truncate group-hover:text-brand-navy transition-colors mb-0.5">
                                                        {session.title}
                                                    </h3>
                                                    <div className="flex items-center gap-3 text-[10px] sm:text-xs text-slate-400">
                                                        <div className="flex items-center gap-1">
                                                            <MessageSquare size={10} />
                                                            <span>{session.message_count} msgs</span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <Clock size={10} />
                                                            <span>{formatTimeAgo(session.updated_at)}</span>
                                                        </div>
                                                    </div>
                                                </>
                                            )}
                                        </div>

                                        {/* Action buttons (hidden in select mode) */}
                                        {!selectMode && (
                                            <div className="flex-shrink-0 flex items-center gap-2">
                                                <button onClick={(e) => handleEditClick(e, session)}
                                                    className="w-8 h-8 rounded-full bg-slate-50 flex items-center justify-center hover:bg-blue-50 transition-colors"
                                                    title="Edit chat title">
                                                    <Edit2 size={14} className="text-slate-400 hover:text-brand-navy transition-colors" />
                                                </button>
                                                <button onClick={(e) => handleDeleteClick(e, session)}
                                                    className="w-8 h-8 rounded-full bg-slate-50 flex items-center justify-center hover:bg-red-50 transition-colors"
                                                    title="Delete chat">
                                                    <Trash2 size={14} className="text-slate-400 hover:text-red-500 transition-colors" />
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            );
                        })}

                        {/* Infinite Scroll Trigger */}
                        {!searchTerm && hasMore && (
                            <div ref={observerTarget} className="h-10 flex items-center justify-center">
                                {loadingMore && (
                                    <div className="flex items-center gap-2 text-sm text-slate-500">
                                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-brand-navy"></div>
                                        Loading more...
                                    </div>
                                )}
                            </div>
                        )}

                        {!searchTerm && !hasMore && sessions.length > 0 && (
                            <div className="text-center py-4 text-xs text-slate-400">
                                No more chats to load
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Floating Bulk Delete Toolbar */}
            {selectMode && selectedIds.size > 0 && (
                <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 bg-white border border-slate-200 rounded-2xl shadow-xl px-5 py-3">
                    <span className="text-sm font-medium text-slate-700">{selectedIds.size} selected</span>
                    <button
                        onClick={handleBulkDeleteClick}
                        className="flex items-center gap-2 px-4 py-1.5 text-sm font-medium text-white bg-red-500 rounded-lg hover:bg-red-600 transition-colors"
                    >
                        <Trash2 size={14} />
                        Delete
                    </button>
                </div>
            )}
        </div>
    );
}

export default ChatHistoryPage;
