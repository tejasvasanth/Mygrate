import { Typography } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import { brand } from '@/theme';
import { DB_LABELS } from '@/lib/utils';
import { DB_FAMILY, type DbFamily, type DbType } from '@/types';

const { Text } = Typography;

/** Per-family accent, used only as a small dot so the palette stays green. */
const dotColor: Record<DbFamily, string> = {
  postgres: '#336791',
  mysql: '#E48E00',
  mongodb: '#13AA52',
  sqlite: '#5C6F7E',
  sqlserver: '#A91D22',
  bigquery: '#4285F4',
  dynamodb: '#527FFF',
  neo4j: '#018BFF',
};

export function DbChip({ type, size = 'default' }: { type: DbType; size?: 'small' | 'default' }) {
  const small = size === 'small';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        padding: small ? '2px 9px' : '4px 11px',
        borderRadius: 99,
        border: `1px solid ${brand.border}`,
        background: brand.surfaceSoft,
        fontSize: small ? 12 : 13,
        fontWeight: 500,
        color: brand.inkSoft,
        whiteSpace: 'nowrap',
      }}
    >
      <span
        style={{
          width: 7,
          height: 7,
          borderRadius: 99,
          background: dotColor[DB_FAMILY[type]],
          flexShrink: 0,
        }}
      />
      {DB_LABELS[type]}
    </span>
  );
}

/** "MySQL → PostgreSQL" pair used across cards and headers. */
export function DbPair({
  source,
  target,
  size = 'default',
}: {
  source: DbType;
  target: DbType;
  size?: 'small' | 'default';
}) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <DbChip type={source} size={size} />
      <Text type="secondary" style={{ fontSize: 12, lineHeight: 1 }}>
        <ArrowRightOutlined />
      </Text>
      <DbChip type={target} size={size} />
    </span>
  );
}
