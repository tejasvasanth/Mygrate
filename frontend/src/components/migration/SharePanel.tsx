import { useState } from 'react';
import {
  App as AntApp,
  Alert,
  Button,
  Card,
  Input,
  Radio,
  Space,
  Switch,
  Typography,
} from 'antd';
import { CopyOutlined, ShareAltOutlined } from '@ant-design/icons';
import { useShareMigration } from '@/hooks/useMigration';
import { apiErrorMessage } from '@/lib/api';
import { brand } from '@/theme';
import type { ShareResponse, ShareVisibility } from '@/types';

const { Text, Paragraph } = Typography;

/** T3-2 + T3-5 — public report link and README badge. */
export function SharePanel({ jobId }: { jobId: string }) {
  const { message } = AntApp.useApp();
  const share = useShareMigration();
  const [visibility, setVisibility] = useState<ShareVisibility>('public');
  const [redactNames, setRedactNames] = useState(true);
  const [result, setResult] = useState<ShareResponse | null>(null);

  const apply = (next: Partial<{ visibility: ShareVisibility; redactNames: boolean }>) => {
    const payload = {
      id: jobId,
      visibility: next.visibility ?? visibility,
      redactNames: next.redactNames ?? redactNames,
    };
    share.mutate(payload, {
      onSuccess: setResult,
      onError: (e) => message.error(apiErrorMessage(e)),
    });
  };

  const copy = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      message.success(`${label} copied`);
    } catch {
      message.error('Could not copy to clipboard');
    }
  };

  return (
    <Card
      variant="outlined"
      className="glass-panel"
      style={{ borderRadius: 14 }}
      styles={{ body: { padding: 22 } }}
      title={
        <Space>
          <ShareAltOutlined style={{ color: brand.green600 }} />
          <Text strong>Share this migration</Text>
        </Space>
      }
    >
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Space direction="vertical" size={6}>
          <Text strong style={{ fontSize: 13 }}>
            Who can see it
          </Text>
          <Radio.Group
            value={visibility}
            onChange={(e) => {
              setVisibility(e.target.value);
              apply({ visibility: e.target.value });
            }}
            optionType="button"
            buttonStyle="solid"
            options={[
              { label: 'Private', value: 'private' },
              { label: 'Team only', value: 'team' },
              { label: 'Public', value: 'public' },
            ]}
          />
        </Space>

        <Space size={10} align="start">
          <Switch
            checked={redactNames}
            onChange={(checked) => {
              setRedactNames(checked);
              apply({ redactNames: checked });
            }}
          />
          <Space direction="vertical" size={0}>
            <Text strong style={{ fontSize: 13 }}>
              Redact table names
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Tables appear as table_1, table_2… Connection strings, credentials and
              column names are never included either way.
            </Text>
          </Space>
        </Space>

        {!result ? (
          <Button
            type="primary"
            loading={share.isPending}
            onClick={() => apply({})}
            icon={<ShareAltOutlined />}
          >
            Create share link
          </Button>
        ) : (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {result.visibility === 'private' ? (
              <Alert
                type="info"
                showIcon
                message="This report is private"
                description="The link below will return a 404 until you set visibility to Team or Public."
              />
            ) : null}

            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              <Text strong style={{ fontSize: 13 }}>
                Report link
              </Text>
              <Space.Compact style={{ width: '100%' }}>
                <Input readOnly value={result.report_url} />
                <Button
                  icon={<CopyOutlined />}
                  onClick={() => copy(result.report_url, 'Link')}
                />
              </Space.Compact>
            </Space>

            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              <Text strong style={{ fontSize: 13 }}>
                README badge
              </Text>
              <Input.TextArea readOnly rows={3} value={result.badge_markdown} />
              <Space>
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => copy(result.badge_markdown, 'Markdown')}
                >
                  Copy markdown
                </Button>
                {result.visibility !== 'private' ? (
                  <img
                    src={result.badge_url}
                    alt="Migrated with Migrate"
                    style={{ height: 20 }}
                  />
                ) : null}
              </Space>
            </Space>

            <Paragraph type="secondary" style={{ fontSize: 12, margin: 0 }}>
              Anyone with the link can view the redacted summary. Set visibility to
              Private at any time to revoke it immediately.
            </Paragraph>
          </Space>
        )}
      </Space>
    </Card>
  );
}
