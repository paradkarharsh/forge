import { describe, it, expect } from 'vitest';
import { parseUnifiedDiff } from '../lib/utils/diff-parser';

describe('Diff Parser Utility', () => {
  it('parses unified diff header and hunks correctly', () => {
    const rawDiff = `--- a/src/hello.ts
+++ b/src/hello.ts
@@ -1,4 +1,5 @@
 import { logger } from './logger';
-const x = 1;
+const x = 2;
+const y = 3;
 export default x;`;

    const parsed = parseUnifiedDiff(rawDiff);

    expect(parsed.fromFile).toBe('src/hello.ts');
    expect(parsed.toFile).toBe('src/hello.ts');
    expect(parsed.hunks).toHaveLength(1);
    expect(parsed.additions).toBe(2);
    expect(parsed.deletions).toBe(1);

    const hunk = parsed.hunks[0];
    expect(hunk.oldStart).toBe(1);
    expect(hunk.newStart).toBe(1);

    // Verify line numbering
    const delLine = hunk.lines.find((l) => l.type === 'delete');
    expect(delLine?.content).toBe('const x = 1;');
    expect(delLine?.oldLineNumber).toBe(2);

    const addLines = hunk.lines.filter((l) => l.type === 'add');
    expect(addLines).toHaveLength(2);
    expect(addLines[0].content).toBe('const x = 2;');
    expect(addLines[0].newLineNumber).toBe(2);
    expect(addLines[1].content).toBe('const y = 3;');
    expect(addLines[1].newLineNumber).toBe(3);
  });

  it('handles empty or non-string diff gracefully', () => {
    expect(parseUnifiedDiff('')).toEqual({ hunks: [], additions: 0, deletions: 0 });
    // @ts-expect-error test non-string input
    expect(parseUnifiedDiff(null)).toEqual({ hunks: [], additions: 0, deletions: 0 });
  });

  it('handles added file diff with only additions', () => {
    const rawDiff = `--- /dev/null
+++ b/new-file.txt
@@ -0,0 +1,2 @@
+Line 1
+Line 2`;

    const parsed = parseUnifiedDiff(rawDiff);
    expect(parsed.toFile).toBe('new-file.txt');
    expect(parsed.additions).toBe(2);
    expect(parsed.deletions).toBe(0);
    expect(parsed.hunks[0].lines).toHaveLength(2);
    expect(parsed.hunks[0].lines[0].newLineNumber).toBe(1);
    expect(parsed.hunks[0].lines[1].newLineNumber).toBe(2);
  });

  it('handles deleted file diff with only deletions', () => {
    const rawDiff = `--- a/deleted.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-Line 1
-Line 2`;

    const parsed = parseUnifiedDiff(rawDiff);
    expect(parsed.fromFile).toBe('deleted.txt');
    expect(parsed.additions).toBe(0);
    expect(parsed.deletions).toBe(2);
    expect(parsed.hunks[0].lines[0].oldLineNumber).toBe(1);
    expect(parsed.hunks[0].lines[1].oldLineNumber).toBe(2);
  });
});
