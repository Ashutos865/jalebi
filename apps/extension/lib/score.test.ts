import { describe, it, expect } from 'vitest';
import { scoreBand, readinessStyle, priorityStyle } from './score';

describe('scoreBand', () => {
  it('maps scores to the right band', () => {
    expect(scoreBand(95).label).toBe('Excellent');
    expect(scoreBand(85).label).toBe('Strong');
    expect(scoreBand(70).label).toBe('Needs work');
    expect(scoreBand(40).label).toBe('Weak');
  });
  it('returns a hex colour for every band', () => {
    for (const s of [95, 85, 70, 40]) {
      expect(scoreBand(s).hex).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});

describe('style maps', () => {
  it('cover every readiness and priority value', () => {
    expect(readinessStyle['Ready to Publish'].dot).toBeTruthy();
    expect(readinessStyle['Not Ready'].dot).toBeTruthy();
    expect(priorityStyle.critical.label).toBe('Critical');
    expect(priorityStyle.low.label).toBe('Low');
  });
});
