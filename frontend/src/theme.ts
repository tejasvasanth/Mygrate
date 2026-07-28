import type { ThemeConfig } from 'antd';

/**
 * Brand palette — white surfaces, green accents.
 * Kept as plain constants so non-antd surfaces (xterm, charts, raw CSS)
 * can share the exact same values.
 */
export const brand = {
  green50: '#F0FDF4',
  green100: '#DCFCE7',
  green200: '#BBF7D0',
  green300: '#86EFAC',
  green500: '#22C55E',
  green600: '#16A34A',
  green700: '#15803D',
  green900: '#14532D',

  ink: '#0F1B14',
  inkSoft: '#4B5A52',
  inkMuted: '#7C8A83',

  surface: '#FFFFFF',
  surfaceSoft: '#F7FAF8',
  border: '#E4EDE7',
} as const;

/** Status colour mapping, shared by badges, charts and the terminal. */
export const statusColor: Record<string, string> = {
  pending: brand.inkMuted,
  analyzing: '#0EA5E9',
  profiling: '#6366F1',
  planning: '#A855F7',
  awaiting_approval: '#F59E0B',
  executing: brand.green600,
  cancelled: brand.inkMuted,
  validating: '#F59E0B',
  completed: brand.green700,
  failed: '#DC2626',
};

export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: brand.green600,
    colorSuccess: brand.green600,
    colorInfo: brand.green600,
    colorLink: brand.green700,

    colorTextBase: brand.ink,
    colorBgBase: brand.surface,
    colorBgLayout: 'transparent',
    colorBorder: brand.border,
    colorBorderSecondary: brand.border,
    colorBgContainer: 'rgba(255, 255, 255, 0.78)',

    borderRadius: 10,
    controlHeight: 38,
    fontSize: 14,
    fontFamily:
      "'Satoshi', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",

    // Slightly slower than default so transitions read as calm, not snappy.
    motionUnit: 0.12,
    boxShadowTertiary: '0 1px 2px rgba(15, 27, 20, 0.04)',
  },
  components: {
    Layout: {
      headerBg: 'rgba(255, 255, 255, 0.72)',
      siderBg: 'rgba(255, 255, 255, 0.78)',
      bodyBg: 'transparent',
      headerHeight: 62,
    },
    Menu: {
      itemSelectedBg: brand.green50,
      itemSelectedColor: brand.green700,
      itemHoverBg: brand.green50,
      itemHoverColor: brand.green700,
      itemBorderRadius: 8,
      itemMarginInline: 8,
      itemBg: 'transparent',
    },
    Card: {
      headerFontSize: 15,
      paddingLG: 22,
      colorBgContainer: 'rgba(255, 255, 255, 0.78)',
    },
    Button: {
      primaryShadow: '0 1px 2px rgba(22, 163, 74, 0.18)',
      fontWeight: 500,
    },
    Steps: {
      colorPrimary: brand.green600,
    },
    Table: {
      headerBg: 'rgba(247, 250, 248, 0.7)',
      headerColor: brand.inkSoft,
      rowHoverBg: brand.green50,
    },
    Progress: {
      defaultColor: brand.green600,
    },
    Tag: {
      defaultBg: brand.green50,
      defaultColor: brand.green700,
    },
  },
};
