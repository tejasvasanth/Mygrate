import { useCallback, useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { Card, Space, Typography } from 'antd';
import { useMigrationLogs } from '@/hooks/useMigration';
import { useMigrationRealtime } from '@/hooks/useMigrationRealtime';
import { formatTimestamp } from '@/lib/utils';
import type { LogLevel, MigrationLog } from '@/types';

const { Text } = Typography;

/** ANSI colours tuned to the green-on-dark terminal palette. */
const LEVEL_ANSI: Record<LogLevel, string> = {
  info: '\x1b[38;2;148;163;158m',
  success: '\x1b[38;2;74;222;128m',
  warning: '\x1b[38;2;251;191;36m',
  error: '\x1b[38;2;248;113;113m',
};

const RESET = '\x1b[0m';
const DIM = '\x1b[38;2;92;110;100m';
const AGENT = '\x1b[38;2;125;211;252m';

function formatLine(log: MigrationLog): string {
  const time = `${DIM}${formatTimestamp(log.created_at)}${RESET}`;
  const agent = `${AGENT}${log.agent.padEnd(20)}${RESET}`;
  const message = `${LEVEL_ANSI[log.level]}${log.message}${RESET}`;
  return `${time}  ${agent}  ${message}\r\n`;
}

/**
 * Live migration log. Historical lines come from the API; new lines arrive
 * over Supabase Realtime and are appended without re-rendering the buffer.
 */
export function ProgressTerminal({ jobId }: { jobId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const writtenIds = useRef<Set<string>>(new Set());

  const { data: logs } = useMigrationLogs(jobId);

  // Append a line only once, even if it arrives via both the query and Realtime.
  const appendLog = useCallback((log: MigrationLog) => {
    if (!termRef.current || writtenIds.current.has(log.id)) return;
    writtenIds.current.add(log.id);
    termRef.current.write(formatLine(log));
  }, []);

  useMigrationRealtime(jobId, appendLog);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      fontSize: 12.5,
      fontFamily: "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace",
      lineHeight: 1.5,
      cursorBlink: false,
      disableStdin: true,
      convertEol: true,
      theme: {
        background: '#0C1410',
        foreground: '#D7E4DC',
        selectionBackground: '#1F3A2B',
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    termRef.current = term;

    const observer = new ResizeObserver(() => {
      try {
        fitAddon.fit();
      } catch {
        // Fit can throw while the container is detached — safe to ignore.
      }
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      term.dispose();
      termRef.current = null;
      writtenIds.current.clear();
    };
  }, []);

  // Backfill history once the terminal exists.
  useEffect(() => {
    if (!termRef.current || !logs) return;
    logs.forEach(appendLog);
  }, [logs, appendLog]);

  return (
    <Card
      variant="outlined"
      className="glass-panel"
      style={{ borderRadius: 14 }}
      styles={{ body: { padding: 16 } }}
      title={
        <Space size={8}>
          <span className="pulse-dot" />
          <Text strong style={{ fontSize: 14 }}>
            Live migration log
          </Text>
        </Space>
      }
    >
      <div className="terminal-shell">
        <div ref={containerRef} style={{ height: 340 }} />
      </div>
    </Card>
  );
}
