import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff } from 'lucide-react';

// ─── Hardcoded credentials ────────────────────────────────────────────────────
// Change these whenever needed — no backend required
const CREDENTIALS = {
    admin: { password: 'admin@2025', role: 'admin' },
    user:  { password: 'user@2025',  role: 'user'  },
};
// ─────────────────────────────────────────────────────────────────────────────

function LoginPage({ onLogin }) {
    const navigate = useNavigate();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [rememberMe, setRememberMe] = useState(false);
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const handleSignIn = (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        // Small artificial delay so it feels like auth is happening
        setTimeout(() => {
            const entry = CREDENTIALS[username.trim().toLowerCase()];

            // If credentials match a known user → use that role
            // Otherwise (empty or unknown) → log in as normal user
            const role = (entry && entry.password === password) ? entry.role : 'user';

            // Clear previous session data
            sessionStorage.removeItem('app_chat_history');

            if (onLogin) onLogin(role);
            navigate('/chat');
        }, 600);
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-navy via-brand-navy-light to-brand-navy p-4">
            {/* Login Card */}
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-8">
                {/* Logo */}
                <div className="flex justify-center mb-6">
                    <img src="/logo/logo.png" alt="Company Logo" className="h-16 w-16 object-contain bg-white p-2 rounded-md" />
                </div>

                {/* Title */}
                <div className="text-center mb-8">
                    <h1 className="text-xl font-bold text-slate-900 mb-1">
                        Data Analytics Platform
                    </h1>
                    <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">
                        Business Intelligence
                    </p>
                </div>

                {/* Login Form */}
                <form onSubmit={handleSignIn} className="space-y-5">
                    {/* Username Field */}
                    <div>
                        <label className="block text-xs font-medium text-slate-600 mb-2 uppercase">
                            Username
                        </label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-navy focus:border-transparent transition"
                            placeholder="Enter username"
                            autoComplete="username"
                        />
                    </div>

                    {/* Password Field */}
                    <div>
                        <label className="block text-xs font-medium text-slate-600 mb-2 uppercase">
                            Password
                        </label>
                        <div className="relative">
                            <input
                                type={showPassword ? 'text' : 'password'}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-navy focus:border-transparent transition pr-10"
                                placeholder="Enter password"
                                autoComplete="current-password"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition"
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    {/* Remember Me */}
                    <div className="flex items-center">
                        <input
                            type="checkbox"
                            id="remember"
                            checked={rememberMe}
                            onChange={(e) => setRememberMe(e.target.checked)}
                            className="w-4 h-4 text-brand-navy bg-slate-50 border-slate-300 rounded focus:ring-brand-navy focus:ring-2"
                        />
                        <label htmlFor="remember" className="ml-2 text-sm text-slate-600">
                            Remember me
                        </label>
                    </div>

                    {/* Sign In Button */}
                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-brand-navy hover:bg-opacity-90 disabled:opacity-70 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-lg transition-all shadow-md hover:shadow-lg text-sm uppercase tracking-wide flex items-center justify-center gap-2"
                    >
                        {isLoading ? (
                            <>
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                Signing in…
                            </>
                        ) : (
                            'Sign In'
                        )}
                    </button>
                </form>

                {/* Active Directory Status */}
                <div className="mt-6 text-center">
                    <p className="text-xs text-slate-500 mb-2">Active Directory Authentication</p>
                    <div className="flex items-center justify-center gap-2">
                        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span className="text-xs text-slate-600 font-medium">
                            Connected to Active Directory
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default LoginPage;
