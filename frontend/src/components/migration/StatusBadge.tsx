import { Tag, Tooltip } from 'antd';
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
  LoadingOutlined,
} from '@ant-design/icons';
import { statusColor } from '@/theme';
import { STATUS_LABELS, isActive } from '@/lib/utils';
import type { MigrationStatus } from '@/types';

interface Props {
  status: MigrationStatus;
  showLabel?: boolean;
}

/** Status pill. Active states get a spinner so motion signals real work. */
export function StatusBadge({ status, showLabel = true }: Props) {
  const color = statusColor[status];

  const icon = isActive(status) ? (
    <LoadingOutlined spin />
  ) : status === 'completed' ? (
    <CheckCircleFilled />
  ) : status === 'failed' ? (
    <CloseCircleFilled />
  ) : (
    <ClockCircleOutlined />
  );

  return (
    <Tooltip title={STATUS_LABELS[status]}>
      <Tag
        icon={icon}
        style={{
          color,
          background: `${color}12`,
          border: `1px solid ${color}2E`,
          borderRadius: 99,
          paddingInline: 10,
          fontWeight: 500,
          margin: 0,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        {showLabel ? STATUS_LABELS[status] : null}
      </Tag>
    </Tooltip>
  );
}
