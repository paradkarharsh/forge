export type DiffLineType = 'header' | 'hunk' | 'add' | 'delete' | 'context';

export interface DiffLine {
  readonly type: DiffLineType;
  readonly content: string;
  readonly oldLineNumber?: number;
  readonly newLineNumber?: number;
}

export interface DiffHunk {
  readonly header: string;
  readonly oldStart: number;
  readonly oldLines: number;
  readonly newStart: number;
  readonly newLines: number;
  readonly lines: DiffLine[];
}

export interface ParsedDiff {
  readonly fromFile?: string;
  readonly toFile?: string;
  readonly hunks: DiffHunk[];
  readonly additions: number;
  readonly deletions: number;
}

const HUNK_HEADER_REGEX = /^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$/;

/**
 * Parse a unified diff string into structured hunks and lines with line numbers.
 */
export function parseUnifiedDiff(rawDiff: string): ParsedDiff {
  if (!rawDiff || typeof rawDiff !== 'string') {
    return { hunks: [], additions: 0, deletions: 0 };
  }

  const rawLines = rawDiff.split(/\r?\n/);
  const hunks: DiffHunk[] = [];
  let fromFile: string | undefined;
  let toFile: string | undefined;
  let additions = 0;
  let deletions = 0;

  let currentHunk: DiffHunk | null = null;
  let currentOldLine = 0;
  let currentNewLine = 0;

  for (const line of rawLines) {
    if (line.startsWith('--- ')) {
      fromFile = line.slice(4).trim().replace(/^[ab]\//, '');
      continue;
    }
    if (line.startsWith('+++ ')) {
      toFile = line.slice(4).trim().replace(/^[ab]\//, '');
      continue;
    }

    const hunkMatch = line.match(HUNK_HEADER_REGEX);
    if (hunkMatch) {
      const oldStart = parseInt(hunkMatch[1], 10);
      const oldLen = hunkMatch[2] !== undefined ? parseInt(hunkMatch[2], 10) : 1;
      const newStart = parseInt(hunkMatch[3], 10);
      const newLen = hunkMatch[4] !== undefined ? parseInt(hunkMatch[4], 10) : 1;

      currentOldLine = oldStart;
      currentNewLine = newStart;

      currentHunk = {
        header: line,
        oldStart,
        oldLines: oldLen,
        newStart,
        newLines: newLen,
        lines: [],
      };
      hunks.push(currentHunk);
      continue;
    }

    if (!currentHunk) {
      // Line before any hunk
      continue;
    }

    if (line.startsWith('+')) {
      additions++;
      currentHunk.lines.push({
        type: 'add',
        content: line.slice(1),
        newLineNumber: currentNewLine++,
      });
    } else if (line.startsWith('-')) {
      deletions++;
      currentHunk.lines.push({
        type: 'delete',
        content: line.slice(1),
        oldLineNumber: currentOldLine++,
      });
    } else if (line.startsWith(' ')) {
      currentHunk.lines.push({
        type: 'context',
        content: line.slice(1),
        oldLineNumber: currentOldLine++,
        newLineNumber: currentNewLine++,
      });
    } else if (line.startsWith('\\')) {
      // \ No newline at end of file
      currentHunk.lines.push({
        type: 'context',
        content: line,
      });
    } else if (line.length > 0) {
      // Fallback for context lines without leading space
      currentHunk.lines.push({
        type: 'context',
        content: line,
        oldLineNumber: currentOldLine++,
        newLineNumber: currentNewLine++,
      });
    }
  }

  return {
    fromFile,
    toFile,
    hunks,
    additions,
    deletions,
  };
}
