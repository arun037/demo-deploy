import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  MessageSquare,
  Flame,
  LayoutDashboard,
  FileText,
  Clock,
  Bell,
  Settings,
  User,
  Menu,
  Volume2,
  Lightbulb,
  BrainCircuit
} from 'lucide-react';

import { config } from '../config.js';
import TalkbackToggle from './TalkbackToggle.jsx';
import { useTalkback } from '../hooks/useTalkback.jsx';
import { getAssetPath, isExtension } from '../utils/extensionContext.js';
import { useContainerWidth } from '../hooks/useContainerWidth.js';

function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [isMenuOpen, setIsMenuOpen] = React.useState(false);
  const [isBackendConnected, setIsBackendConnected] = useState(true);
  const [isMicOn, setIsMicOn] = useState(false);
  const { talkbackEnabled, toggleTalkback, isActiveTalkbackSession } = useTalkback();
  const { isNarrow } = useContainerWidth();
  const menuRef = React.useRef(null);
  const buttonRef = React.useRef(null);

  React.useEffect(() => {
    function handleClickOutside(event) {
      if (isMenuOpen &&
        menuRef.current && !menuRef.current.contains(event.target) &&
        buttonRef.current && !buttonRef.current.contains(event.target)) {
        setIsMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isMenuOpen]);

  // All 5 navigation tabs
  const navItems = [
    { to: '/chat', label: 'Chat', icon: MessageSquare },
    { to: '/popular', label: 'Popular', icon: Flame },
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/reports', label: 'Reports', icon: FileText },
    { to: '/history', label: 'History', icon: Clock },
    { to: '/insights', label: 'AI Insights', icon: BrainCircuit },

  ];

  const handleMicToggle = () => {
    setIsMicOn(!isMicOn);
    // TODO: Implement actual voice/audio functionality
    console.log('Mic toggled:', !isMicOn);
  };

  const handleLogout = () => {
    localStorage.removeItem('app_auth_token');
    localStorage.removeItem('app_user_email');
    localStorage.removeItem('app_auth');
    localStorage.removeItem('app_role');
    navigate('/login');
  };

  // Backend health check polling
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 second timeout for busy servers

        const response = await fetch(`${config.API.BASE_URL}/api/health`, {
          signal: controller.signal
        });

        clearTimeout(timeoutId);
        setIsBackendConnected(response.ok);
      } catch (error) {
        console.warn('Backend health check failed:', error.message);
        // Don't immediately turn red on timeout if it was previously connected?
        // strict check for now, but timeout is longer
        setIsBackendConnected(false);
      }
    };

    // Check immediately on mount
    checkBackendHealth();

    // Poll every 30 seconds to reduce load
    const interval = setInterval(checkBackendHealth, 30000);

    return () => clearInterval(interval);
  }, []);

  const handleMenuToggle = () => {
    setIsMenuOpen(!isMenuOpen);
    console.log('Menu toggled:', !isMenuOpen);
  };

  // Use full height in extension context, screen height in web context
  const containerClass = isExtension() ? 'h-full' : 'h-screen';
  
  return (
    <div className={`${containerClass} overflow-hidden flex flex-col bg-slate-50 text-slate-900 font-sans`}>
      {/* Header */}
      <header className="bg-brand-navy text-white shadow-md relative">
        <div className="mx-auto w-full px-2 sm:px-4 py-2 sm:py-2.5">
          <div className="flex items-center justify-between">
            {/* Logo Section */}
            <div className="flex items-center gap-2 sm:gap-3">
              <img src={getAssetPath('logo/logo.png')} alt="Company Logo" className="h-8 w-8 sm:h-10 sm:w-10 object-contain bg-white p-1 rounded-sm" />
              <div className="flex flex-col leading-tight">
                {/* Show abbreviated name on narrow screens, full name on wider screens */}
                <span className="text-sm sm:text-base font-bold tracking-wide">
                  <span className="hidden sm:inline">DATA ANALYTICS PLATFORM</span>
                  <span className="text-[13px] sm:hidden">ANALYTICS PLATFORM</span>
                </span>
                <span className="text-[9px] sm:text-[10px] font-medium opacity-90 uppercase tracking-wider">Business Intelligence</span>
              </div>
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-1.5 sm:gap-3">
              {/* Status Indicator - Dynamic based on backend connection */}
              <div className="flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${isBackendConnected ? 'bg-green-400' : 'bg-red-500'} animate-pulse`}
                  title={isBackendConnected ? 'Backend Connected' : 'Backend Disconnected'}
                ></div>
              </div>

              {/* Talkback Toggle */}
              <TalkbackToggle
                enabled={talkbackEnabled}
                onToggle={toggleTalkback}
                isActive={isActiveTalkbackSession}
              />

              <button
                ref={buttonRef}
                onClick={handleMenuToggle}
                className={`p-1 sm:p-1.5 rounded-md transition ${isMenuOpen
                  ? 'bg-blue-700'
                  : 'bg-brand-navy/50 hover:bg-brand-navy'
                  }`}
                title="Menu"
              >
                <Menu size={16} className="sm:w-[18px] sm:h-[18px]" />
              </button>
            </div>
          </div>
        </div>

        {/* Dropdown Menu */}
        {isMenuOpen && (
          <div ref={menuRef} className="absolute right-2 sm:right-4 top-14 sm:top-16 bg-white text-slate-800 rounded-lg shadow-xl border border-slate-200 py-2 min-w-[200px] z-50">
            {/* User Profile Section */}
            <div className="px-4 py-3 border-b border-slate-200">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-brand-navy flex items-center justify-center text-white font-semibold">
                  A
                </div>
                <div className="flex-1">
                  <div className="font-semibold text-sm text-slate-800">Administrator</div>
                  <div className="text-xs text-slate-500">ADMINISTRATOR</div>
                </div>
              </div>
            </div>

            {/* Menu Items */}
            <div className="py-1">
              <button className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 flex items-center gap-3 transition-colors">
                <Settings size={16} className="text-slate-600" />
                <span className="text-slate-700">Settings</span>
              </button>
              <button className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 flex items-center gap-3 transition-colors">
                <User size={16} className="text-slate-600" />
                <span className="text-slate-700">Profile</span>
              </button>
              <button className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 flex items-center gap-3 transition-colors">
                <Bell size={16} className="text-slate-600" />
                <span className="text-slate-700">Notifications</span>
              </button>
              <button className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 flex items-center gap-3 transition-colors">
                <Lightbulb size={16} className="text-slate-600" />
                <span className="text-slate-700">Help</span>
              </button>
            </div>

            <div className="border-t border-slate-200 my-1"></div>

            {/* Additional Actions */}
            <div className="py-1">
              <button
                onClick={() => {
                  // Clear current session
                  localStorage.removeItem('app_current_session_id');

                  // If already on chat page, trigger refresh via event
                  if (location.pathname === '/chat') {
                    window.dispatchEvent(new Event('app-new-chat'));
                  } else {
                    // Otherwise navigate to chat (will create new session on mount)
                    navigate('/chat');
                  }
                  setIsMenuOpen(false);
                }}
                className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 flex items-center gap-3 transition-colors"
              >
                <div className="relative">
                  <MessageSquare size={16} className="text-slate-600" />
                  <div className="absolute -top-1 -right-1 w-2 h-2 bg-brand-navy rounded-full border border-white"></div>
                </div>
                <span className="text-slate-700">New Chat</span>
              </button>
              <button className="w-full px-4 py-2.5 text-left text-sm hover:bg-slate-50 flex items-center gap-3 transition-colors">
                <FileText size={16} className="text-slate-600" />
                <span className="text-slate-700">Send Feedback</span>
              </button>
            </div>

            <div className="border-t border-slate-200 my-1"></div>

            {/* Sign Out */}
            <button onClick={handleLogout} className="w-full px-4 py-2.5 text-left text-sm hover:bg-red-50 flex items-center gap-3 transition-colors text-red-600">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
              <span className="font-medium">Sign Out</span>
            </button>
          </div>
        )}
      </header>

      {/* Navigation Tabs - White Background */}
      <nav className="bg-white border-b border-slate-200 shadow-sm">
        <div className="flex items-center justify-around px-1 sm:px-2">
          {navItems.filter(item => item.label !== 'AI Insights').map((item) => (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 sm:gap-1 ${isNarrow ? 'px-1.5 py-1.5' : 'px-4 sm:px-8 py-1.5 sm:py-2'} border-b-2 transition-all duration-200 ${isActive
                  ? 'border-brand-navy text-brand-navy'
                  : 'border-transparent text-slate-500 hover:text-brand-navy hover:bg-slate-50'
                }`
              }
            >
              <item.icon size={isNarrow ? 14 : 18} strokeWidth={2} className="sm:w-[20px] sm:h-[20px]" />
              <span className={`${isNarrow ? 'text-[8px]' : 'text-[10px]'} sm:text-xs font-medium`}>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden relative">
        <div className="h-full w-full overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300 scrollbar-track-slate-100">
          {children}
        </div>
      </main>
    </div>
  );
}

export default Layout;

