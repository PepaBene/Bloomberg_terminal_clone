/* ------------------------------------------------------------------ */
/*  Command Parser — Bloomberg Data Fabric Terminal                    */
/*                                                                     */
/*  Parses structured command syntax from the command bar into a       */
/*  typed ParsedCommand object that the router / dispatcher can act on */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ParsedCommand {
  type: 'security' | 'command' | 'screen' | 'navigate';
  ticker?: string;
  /** Sub-command name, e.g. 'dcf', 'compare', 'filings', 'alerts' */
  command?: string;
  /** Additional positional arguments after the command. */
  args?: string[];
  /** Parsed screen filters — e.g. { pe: { op: '<', value: 15 } } */
  screenFilters?: Record<string, { op: string; value: number }>;
}

/* ------------------------------------------------------------------ */
/*  Regex patterns                                                     */
/* ------------------------------------------------------------------ */

/** A standard uppercase ticker symbol: 1-5 uppercase letters, optionally with a dot (BRK.B) */
const TICKER_RE = /^[A-Z]{1,5}(?:\.[A-Z]{1,2})?$/;

/** A /command token */
const COMMAND_RE = /^\/([a-zA-Z]\w*)$/;

/** A screen filter token: /metric<op><value>  e.g. /pe<15, /roe>20, /div>=3.5 */
const FILTER_RE = /^\/([a-zA-Z]\w*)(<=?|>=?|={1,2})(-?\d+(?:\.\d+)?)$/;

/* ------------------------------------------------------------------ */
/*  Parser                                                             */
/* ------------------------------------------------------------------ */

export function parseCommand(input: string): ParsedCommand {
  const raw = input.trim();
  if (raw.length === 0) {
    return { type: 'navigate', command: '' };
  }

  const tokens = raw.split(/\s+/);
  const first = tokens[0]!;

  /* ----- Case 1: Bare navigation command — `/alerts`, `/macro` ----- */
  const navMatch = COMMAND_RE.exec(first);
  if (navMatch && tokens.length === 1 && !TICKER_RE.test(first)) {
    return { type: 'navigate', command: navMatch[1] };
  }

  /* ----- Case 2: `screen /pe<15 /roe>20` — screener ---- */
  if (first.toLowerCase() === 'screen') {
    const filters: Record<string, { op: string; value: number }> = {};
    for (let i = 1; i < tokens.length; i++) {
      const fm = FILTER_RE.exec(tokens[i]!);
      if (fm) {
        filters[fm[1]!.toLowerCase()] = {
          op: fm[2]!,
          value: Number(fm[3]),
        };
      }
    }
    return { type: 'screen', screenFilters: filters };
  }

  /* ----- Case 3: Ticker-based commands (AAPL, AAPL /dcf, …) ----- */
  const upperFirst = first.toUpperCase();
  if (TICKER_RE.test(upperFirst)) {
    /* 3a: Bare ticker — `AAPL` */
    if (tokens.length === 1) {
      return { type: 'security', ticker: upperFirst };
    }

    /* 3b: Ticker + /command [args…] — `AAPL /dcf` or `AAPL /compare MSFT GOOGL` */
    const cmdToken = tokens[1]!;
    const cmdMatch = COMMAND_RE.exec(cmdToken);
    if (cmdMatch) {
      const args = tokens
        .slice(2)
        .map((t) => t.toUpperCase())
        .filter((t) => t.length > 0);
      return {
        type: 'command',
        ticker: upperFirst,
        command: cmdMatch[1]!.toLowerCase(),
        args: args.length > 0 ? args : undefined,
      };
    }

    /* Fallback: treat everything after the ticker as positional args */
    return {
      type: 'security',
      ticker: upperFirst,
      args: tokens.slice(1),
    };
  }

  /* ----- Case 4: Standalone /command with args — `/alerts high` ----- */
  if (navMatch) {
    const args = tokens.slice(1);
    return {
      type: 'navigate',
      command: navMatch[1],
      args: args.length > 0 ? args : undefined,
    };
  }

  /* ----- Fallback: treat entire input as a bare navigate/search ----- */
  return { type: 'navigate', command: raw };
}
