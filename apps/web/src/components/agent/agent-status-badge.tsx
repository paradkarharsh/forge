'use client';

import {
  Brain,
  CalendarX,
  CheckCircle2,
  Clock,
  Play,
  ShieldAlert,
  Slash,
  TimerOff,
  XCircle,
} from 'lucide-react';
import type { AgentStatus } from '../../lib/api/types';
import { getStatusConfig } from '../../lib/utils/status';

interface AgentStatusBadgeProps {
  readonly status: AgentStatus | string;
  readonly size?: 'sm' | 'md' | 'lg';
  readonly showDot?: boolean;
}

export function AgentStatusBadge({
  status,
  size = 'md',
  showDot = true,
}: AgentStatusBadgeProps) {
  const config = getStatusConfig(status);

  const iconSize = size === 'sm' ? 12 : size === 'lg' ? 16 : 14;

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1.5',
    md: 'text-xs px-2.5 py-1 gap-2',
    lg: 'text-sm px-3 py-1.5 gap-2.5',
  }[size];

  const renderIcon = () => {
    switch (config.iconName) {
      case 'clock':
        return <Clock size={iconSize} className="shrink-0" />;
      case 'brain':
        return <Brain size={iconSize} className="shrink-0" />;
      case 'play':
        return <Play size={iconSize} className="shrink-0" />;
      case 'shield-alert':
        return <ShieldAlert size={iconSize} className="shrink-0" />;
      case 'check-circle':
        return <CheckCircle2 size={iconSize} className="shrink-0" />;
      case 'x-circle':
        return <XCircle size={iconSize} className="shrink-0" />;
      case 'slash':
        return <Slash size={iconSize} className="shrink-0" />;
      case 'timer-off':
        return <TimerOff size={iconSize} className="shrink-0" />;
      case 'calendar-x':
        return <CalendarX size={iconSize} className="shrink-0" />;
      default:
        return <Clock size={iconSize} className="shrink-0" />;
    }
  };

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border transition-colors ${config.badgeClass} ${sizeClasses}`}
      title={config.description}
    >
      {showDot && (
        <span
          className={`h-1.5 w-1.5 rounded-full ${config.dotClass}`}
          aria-hidden="true"
        />
      )}
      {renderIcon()}
      <span>{config.label}</span>
    </span>
  );
}
