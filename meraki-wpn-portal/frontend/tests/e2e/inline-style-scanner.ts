#!/usr/bin/env npx ts-node
/**
 * Inline Style Scanner
 * 
 * Static analysis script to detect inline style={{}} usage in TSX files.
 * Inline styles bypass the CSS dark mode system and must be replaced with Tailwind classes.
 * 
 * Usage:
 *   npx ts-node tests/e2e/inline-style-scanner.ts
 *   npm run lint:inline-styles
 * 
 * Exit codes:
 *   0 - No violations found
 *   1 - Violations found (will fail CI)
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

interface StyleViolation {
  file: string;
  line: number;
  column: number;
  code: string;
  suggestion: string;
}

// Pattern to match inline style={{...}} in JSX
const INLINE_STYLE_PATTERN = /style=\{\{([^}]+(?:\{[^}]*\}[^}]*)*)\}\}/g;

// Patterns that are allowed (truly dynamic values that can't be Tailwind classes)
const ALLOWED_PATTERNS: Array<{ pattern: RegExp; reason: string }> = [
  // CSS custom property overrides (dynamic theming)
  { pattern: /['"]?--[\w-]+['"]?\s*:/, reason: 'CSS custom property override' },
  // Dynamic dimensions from state/props (not hardcoded values)
  { pattern: /height\s*:\s*[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*(?:\s*\+|\s*-|\s*\*|\s*\/|\s*\?|\s*\|)?/, reason: 'Dynamic height' },
  { pattern: /width\s*:\s*[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*(?:\s*\+|\s*-|\s*\*|\s*\/|\s*\?|\s*\|)?/, reason: 'Dynamic width' },
  // Dynamic colors from state/props (e.g., strengthColor, primaryColor, formData.color)
  { pattern: /color\s*:\s*[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*\s*(?:,|\}|\s)/, reason: 'Dynamic color variable' },
  { pattern: /backgroundColor\s*:\s*[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*\s*(?:,|\}|\s)/, reason: 'Dynamic background color' },
  // Transform with dynamic values
  { pattern: /transform\s*:\s*`/, reason: 'Dynamic transform' },
  // Animation with dynamic values
  { pattern: /animation\s*:\s*`/, reason: 'Dynamic animation' },
  // Template literals (dynamic interpolation)
  { pattern: /`[^`]*\$\{/, reason: 'Template literal with interpolation' },
  // Dynamic opacity from state/props
  { pattern: /opacity\s*:\s*[a-zA-Z_$!][\w$!]*(?:\s*\?|\s*\||[^'"])/, reason: 'Dynamic opacity' },
  // Background with linear-gradient or rgba using dynamic values
  { pattern: /background\s*:\s*`/, reason: 'Dynamic background with template literal' },
  // Width/height with fixed icon sizes (48px, 64px buttons are acceptable for icon containers)
  { pattern: /width\s*:\s*['"](?:48|64)px['"].*height\s*:\s*['"](?:48|64)px['"]/, reason: 'Fixed icon container size' },
];

// Map of common inline styles to their Tailwind equivalents
const STYLE_TO_TAILWIND: Record<string, string> = {
  // Backgrounds
  "background: 'var(--gray-100)'": 'bg-gray-100 dark:bg-slate-700',
  "background: 'var(--gray-200)'": 'bg-gray-200 dark:bg-slate-600',
  "background: 'rgba(0, 0, 0, 0.5)'": 'bg-black/50',
  "background: 'rgba(0, 164, 228, 0.1)'": 'bg-meraki-blue/10',
  "background: 'rgba(34, 197, 94, 0.1)'": 'bg-green-500/10',
  "background: 'rgba(239, 68, 68, 0.1)'": 'bg-red-500/10',
  "background: '#fef2f2'": 'bg-red-50 dark:bg-red-950',
  // Colors
  "color: 'var(--meraki-blue)'": 'text-meraki-blue',
  "color: 'var(--gray-400)'": 'text-gray-400 dark:text-slate-400',
  "color: 'var(--gray-600)'": 'text-gray-600 dark:text-slate-300',
  "color: '#22c55e'": 'text-green-500',
  "color: '#ef4444'": 'text-red-500',
  "color: '#f59e0b'": 'text-amber-500',
  // Borders
  "borderBottom: '1px solid var(--gray-200)'": 'border-b border-gray-200 dark:border-slate-700',
  "borderBottom: '1px solid var(--gray-100)'": 'border-b border-gray-100 dark:border-slate-800',
};

/**
 * Check if a style value is allowed based on exception patterns
 */
function isAllowedStyle(styleContent: string): { allowed: boolean; reason?: string } {
  for (const { pattern, reason } of ALLOWED_PATTERNS) {
    if (pattern.test(styleContent)) {
      return { allowed: true, reason };
    }
  }
  return { allowed: false };
}

/**
 * Get a suggestion for replacing an inline style with Tailwind
 */
function getSuggestion(styleContent: string): string {
  // Check for exact matches first
  for (const [inlineStyle, tailwind] of Object.entries(STYLE_TO_TAILWIND)) {
    if (styleContent.includes(inlineStyle.replace(/'/g, "'"))) {
      return `Replace with Tailwind class: ${tailwind}`;
    }
  }

  // Generic suggestions based on property
  if (styleContent.includes('background')) {
    return 'Replace with bg-* class (add dark: variant for dark mode)';
  }
  if (styleContent.includes('color')) {
    return 'Replace with text-* class (add dark: variant for dark mode)';
  }
  if (styleContent.includes('border')) {
    return 'Replace with border-* class (add dark: variant for dark mode)';
  }
  if (styleContent.includes('padding') || styleContent.includes('margin')) {
    return 'Replace with p-*/m-* spacing classes';
  }
  if (styleContent.includes('maxWidth') || styleContent.includes('max-width')) {
    return 'Replace with max-w-* class';
  }

  return 'Replace with equivalent Tailwind CSS classes';
}

/**
 * Scan a single file for inline style violations
 */
function scanFile(filePath: string): StyleViolation[] {
  const violations: StyleViolation[] = [];
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  // Track cumulative position for accurate line numbers
  let currentPos = 0;

  for (let lineIndex = 0; lineIndex < lines.length; lineIndex++) {
    const line = lines[lineIndex];
    const lineStart = currentPos;
    currentPos += line.length + 1; // +1 for newline

    // Find all style={{}} patterns in this line
    let match: RegExpExecArray | null;
    const linePattern = /style=\{\{([^}]+(?:\{[^}]*\}[^}]*)*)\}\}/g;

    while ((match = linePattern.exec(line)) !== null) {
      const styleContent = match[1];
      const { allowed, reason } = isAllowedStyle(styleContent);

      if (!allowed) {
        violations.push({
          file: filePath,
          line: lineIndex + 1,
          column: match.index + 1,
          code: `style={{${styleContent.length > 50 ? styleContent.slice(0, 50) + '...' : styleContent}}}`,
          suggestion: getSuggestion(styleContent),
        });
      }
    }
  }

  return violations;
}

/**
 * Recursively find all TSX files in a directory
 */
function findTsxFiles(dir: string, files: string[] = []): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      // Skip node_modules and test directories
      if (entry.name !== 'node_modules' && entry.name !== '__tests__') {
        findTsxFiles(fullPath, files);
      }
    } else if (entry.isFile() && entry.name.endsWith('.tsx')) {
      files.push(fullPath);
    }
  }

  return files;
}

/**
 * Main scanner function
 */
function runScanner(): { violations: StyleViolation[]; filesScanned: number } {
  const srcDir = path.resolve(__dirname, '../../src');
  const tsxFiles = findTsxFiles(srcDir);
  const allViolations: StyleViolation[] = [];

  for (const file of tsxFiles) {
    const violations = scanFile(file);
    allViolations.push(...violations);
  }

  return { violations: allViolations, filesScanned: tsxFiles.length };
}

/**
 * Format violation for console output
 */
function formatViolation(v: StyleViolation): string {
  const relativePath = path.relative(process.cwd(), v.file);
  return [
    `\x1b[31m✗\x1b[0m ${relativePath}:${v.line}:${v.column}`,
    `  Code: ${v.code}`,
    `  \x1b[33m→ ${v.suggestion}\x1b[0m`,
  ].join('\n');
}

// Run if executed directly (ESM compatible)
const isMain = process.argv[1] && (
  process.argv[1] === fileURLToPath(import.meta.url) ||
  process.argv[1].endsWith('inline-style-scanner.ts')
);

if (isMain) {
  console.log('\n🔍 Scanning for inline styles...\n');

  const { violations, filesScanned } = runScanner();

  if (violations.length === 0) {
    console.log(`\x1b[32m✓\x1b[0m No inline style violations found in ${filesScanned} files.\n`);
    process.exit(0);
  } else {
    console.log(`\x1b[31m✗\x1b[0m Found ${violations.length} inline style violation(s):\n`);

    // Group by file
    const byFile = new Map<string, StyleViolation[]>();
    for (const v of violations) {
      const existing = byFile.get(v.file) || [];
      existing.push(v);
      byFile.set(v.file, existing);
    }

    for (const [file, fileViolations] of byFile) {
      console.log(`\n\x1b[1m${path.relative(process.cwd(), file)}\x1b[0m`);
      for (const v of fileViolations) {
        console.log(`  Line ${v.line}: ${v.code}`);
        console.log(`    \x1b[33m→ ${v.suggestion}\x1b[0m`);
      }
    }

    console.log(`\n\x1b[31mInline styles bypass dark mode CSS.\x1b[0m`);
    console.log('Replace with Tailwind classes and add dark: variants.\n');
    process.exit(1);
  }
}

// Export for use in tests
export { runScanner, scanFile, isAllowedStyle, StyleViolation };
