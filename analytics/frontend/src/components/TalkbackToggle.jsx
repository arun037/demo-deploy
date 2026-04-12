/**
 * TalkbackToggle Component
 * Red/Green speaker button in navigation bar
 * Enables/disables hands-free conversational AI
 */

import React from 'react';
import { Volume2, VolumeX } from 'lucide-react';

function TalkbackToggle({ enabled, onToggle, isActive = false }) {
  return (
    <button
      onClick={onToggle}
      title={enabled ? 'Talkback enabled (click to disable)' : 'Talkback disabled (click to enable)'}
      className={`
        relative p-2 rounded-lg transition-all duration-200
        ${
          enabled
            ? 'bg-green-100 hover:bg-green-200 text-green-700'
            : 'bg-red-100 hover:bg-red-200 text-red-600'
        }
        ${isActive ? 'ring-2 ring-offset-2 ring-green-500' : ''}
        focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-400
      `}
      aria-label={`Talkback ${enabled ? 'enabled' : 'disabled'}`}
      aria-pressed={enabled}
    >
      {enabled ? (
        <Volume2
          size={18}
          className="sm:w-5 sm:h-5"
          strokeWidth={2}
        />
      ) : (
        <VolumeX
          size={18}
          className="sm:w-5 sm:h-5"
          strokeWidth={2}
        />
      )}

      {/* Status indicator dot */}
      <span
        className={`
          absolute top-1 right-1 w-2 h-2 rounded-full
          ${enabled ? 'bg-green-500' : 'bg-red-500'}
        `}
      />

      {/* Optional: Tooltip on hover */}
      <div
        className={`
          absolute bottom-full right-0 mb-2 px-2 py-1 text-xs whitespace-nowrap
          rounded-md opacity-0 pointer-events-none transition-opacity
          ${enabled ? 'bg-green-700 text-white' : 'bg-red-700 text-white'}
          group-hover:opacity-100
        `}
      >
        {enabled ? 'Talkback: ON' : 'Talkback: OFF'}
      </div>
    </button>
  );
}

export default TalkbackToggle;
