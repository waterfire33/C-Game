'use client';

import { useEffect, useState } from 'react';
import type { WorkflowEvent, EventType } from '../lib/workflow-types';
import { EVENT_ICONS, EVENT_LABELS } from '../lib/workflow-types';
import { getRunTimeline } from '../lib/workflow-api';

type TimelineProps = {
  /** The workflow run ID to display timeline for */
  runId: string;
  /** JWT access token for API authentication */
  token: string;
  /** Optional polling interval in ms (0 to disable) */
  pollInterval?: number;
  /** Optional callback when events are loaded */
  onEventsLoaded?: (events: WorkflowEvent[]) => void;
};

/**
 * Format a timestamp for display
 */
function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Get the color class for an event type
 */
function getEventColor(eventType: EventType): string {
  switch (eventType) {
    case 'run_created':
    case 'run_started':
    case 'run_resumed':
      return 'border-blue-500 bg-blue-50';
    case 'run_completed':
    case 'step_completed':
    case 'approval_granted':
      return 'border-green-500 bg-green-50';
    case 'run_failed':
    case 'step_failed':
    case 'approval_denied':
      return 'border-red-500 bg-red-50';
    case 'run_cancelled':
      return 'border-gray-500 bg-gray-50';
    case 'run_paused':
    case 'approval_requested':
      return 'border-orange-500 bg-orange-50';
    case 'step_started':
      return 'border-blue-400 bg-blue-50';
    case 'step_retry_scheduled':
    case 'run_retry_requested':
      return 'border-yellow-500 bg-yellow-50';
    default:
      return 'border-gray-300 bg-gray-50';
  }
}

/**
 * Get event description based on payload
 */
function getEventDescription(event: WorkflowEvent): string | null {
  const { payload, event_type, step_index } = event;

  // Step-related events
  if (step_index !== null && ['step_started', 'step_completed', 'step_failed'].includes(event_type)) {
    return `Step ${step_index}`;
  }

  // Approval events
  if (event_type === 'approval_requested' && step_index !== null) {
    return `Step ${step_index} awaiting approval`;
  }
  if (event_type === 'approval_granted' && step_index !== null) {
    return `Step ${step_index} approved`;
  }
  if (event_type === 'approval_denied') {
    const reason = payload.reason as string | undefined;
    return reason ? `Denied: ${reason}` : 'Approval denied';
  }

  // Failure events
  if (event_type === 'run_failed' || event_type === 'step_failed') {
    const errorMessage = payload.error_message as string | undefined;
    return errorMessage ?? 'Unknown error';
  }

  // Retry events
  if (event_type === 'step_retry_scheduled') {
    const attempt = payload.attempt_number as number | undefined;
    return attempt ? `Retry attempt ${attempt}` : 'Retry scheduled';
  }
  if (event_type === 'run_retry_requested') {
    const count = payload.retry_count as number | undefined;
    return count ? `Retry #${count}` : 'Retry requested';
  }

  return null;
}

/**
 * Single timeline event card
 */
function TimelineEventCard({ event }: { event: WorkflowEvent }) {
  const colorClass = getEventColor(event.event_type);
  const description = getEventDescription(event);

  return (
    <div className={`relative pl-8 pb-6`}>
      {/* Timeline connector line */}
      <div className="absolute left-[11px] top-6 bottom-0 w-0.5 bg-gray-200" />
      
      {/* Event dot */}
      <div className="absolute left-0 top-1 w-6 h-6 rounded-full bg-white border-2 border-gray-300 flex items-center justify-center text-xs">
        {EVENT_ICONS[event.event_type]}
      </div>

      {/* Event card */}
      <div className={`border-l-4 rounded-lg p-3 shadow-sm ${colorClass}`}>
        <div className="flex items-center justify-between">
          <span className="font-medium text-gray-900">
            {EVENT_LABELS[event.event_type]}
          </span>
          <span className="text-xs text-gray-500">
            #{event.sequence_number}
          </span>
        </div>

        <div className="text-xs text-gray-500 mt-1">
          {formatTimestamp(event.created_at)}
        </div>

        {description && (
          <div className="text-sm text-gray-700 mt-2">
            {description}
          </div>
        )}

        {/* Status transition */}
        {event.previous_status && event.new_status && (
          <div className="text-xs text-gray-500 mt-2">
            <span className="font-mono">{event.previous_status}</span>
            {' → '}
            <span className="font-mono">{event.new_status}</span>
          </div>
        )}

        {/* Actor info */}
        {event.actor_user_id && (
          <div className="text-xs text-gray-400 mt-1">
            by user {event.actor_user_id.slice(0, 8)}...
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Loading skeleton for timeline
 */
function TimelineSkeleton() {
  return (
    <div className="animate-pulse">
      {[1, 2, 3].map((i) => (
        <div key={i} className="relative pl-8 pb-6">
          <div className="absolute left-0 top-1 w-6 h-6 rounded-full bg-gray-200" />
          <div className="border-l-4 border-gray-200 rounded-lg p-3 bg-gray-100">
            <div className="h-4 bg-gray-200 rounded w-1/3 mb-2" />
            <div className="h-3 bg-gray-200 rounded w-1/4" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Run Timeline Component
 * 
 * Displays a chronological list of events for a workflow run.
 * Supports optional polling for real-time updates.
 */
export function RunTimeline({
  runId,
  token,
  pollInterval = 0,
  onEventsLoaded,
}: TimelineProps) {
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    let pollTimeoutId: ReturnType<typeof setTimeout> | null = null;

    async function fetchTimeline() {
      try {
        const response = await getRunTimeline(runId, { token });
        if (!mounted) return;

        setEvents(response.events);
        setError(null);
        onEventsLoaded?.(response.events);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to load timeline');
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    async function poll() {
      await fetchTimeline();
      if (mounted && pollInterval > 0) {
        pollTimeoutId = setTimeout(poll, pollInterval);
      }
    }

    poll();

    return () => {
      mounted = false;
      if (pollTimeoutId) {
        clearTimeout(pollTimeoutId);
      }
    };
  }, [runId, token, pollInterval, onEventsLoaded]);

  if (loading) {
    return (
      <div className="p-4">
        <h3 className="text-lg font-semibold mb-4">Run Timeline</h3>
        <TimelineSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <h3 className="text-lg font-semibold mb-4">Run Timeline</h3>
        <div className="text-red-600 bg-red-50 border border-red-200 rounded p-3">
          {error}
        </div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="p-4">
        <h3 className="text-lg font-semibold mb-4">Run Timeline</h3>
        <div className="text-gray-500 text-center py-8">
          No events recorded yet
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h3 className="text-lg font-semibold mb-4">
        Run Timeline
        <span className="text-sm font-normal text-gray-500 ml-2">
          ({events.length} events)
        </span>
      </h3>
      
      <div className="relative">
        {events.map((event) => (
          <TimelineEventCard key={event.id} event={event} />
        ))}
        
        {/* Remove the line from the last event */}
        <div className="absolute left-[11px] bottom-0 h-6 w-0.5 bg-white" />
      </div>
    </div>
  );
}

export default RunTimeline;
