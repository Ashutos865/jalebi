// Score → colour band, shared by the ring, bars, and badges.
import type { Priority, PublicationReadiness } from './types';

export function scoreBand(score: number): { hex: string; label: string } {
  if (score >= 90) return { hex: '#10b981', label: 'Excellent' };
  if (score >= 80) return { hex: '#ff9933', label: 'Strong' };
  if (score >= 65) return { hex: '#f59e0b', label: 'Needs work' };
  return { hex: '#f43f5e', label: 'Weak' };
}

export const readinessStyle: Record<
  PublicationReadiness,
  { bg: string; fg: string; dot: string }
> = {
  'Ready to Publish': { bg: 'rgba(16,185,129,0.15)', fg: '#059669', dot: '#10b981' },
  'Needs Minor Revision': { bg: 'rgba(255,153,51,0.16)', fg: '#c2620a', dot: '#ff9933' },
  'Needs Major Revision': { bg: 'rgba(245,158,11,0.16)', fg: '#b45309', dot: '#f59e0b' },
  'Not Ready': { bg: 'rgba(244,63,94,0.15)', fg: '#e11d48', dot: '#f43f5e' },
};

export const priorityStyle: Record<Priority, { bg: string; fg: string; label: string }> = {
  critical: { bg: 'rgba(244,63,94,0.16)', fg: '#e11d48', label: 'Critical' },
  high: { bg: 'rgba(249,115,22,0.16)', fg: '#ea580c', label: 'High' },
  medium: { bg: 'rgba(255,153,51,0.16)', fg: '#c2620a', label: 'Medium' },
  low: { bg: 'rgba(113,113,122,0.16)', fg: '#71717a', label: 'Low' },
};
