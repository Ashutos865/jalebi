import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('.', import.meta.url)),
    },
  },
  test: {
    // jsdom, not node: the riskiest modules here (checker, rects, editable,
    // overlay) are DOM-driven and are untestable under a node environment.
    environment: 'jsdom',
    include: ['**/*.test.ts', '**/*.test.tsx'],
    exclude: ['node_modules/**', '.output/**', '.wxt/**'],
  },
});
