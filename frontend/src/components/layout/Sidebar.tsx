import { useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Typography } from 'antd';
import {
  AppstoreOutlined,
  DatabaseOutlined,
  MonitorOutlined,
  PlusCircleOutlined,
  RobotOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useMigrationStore } from '@/store/migrationStore';
import { brand } from '@/theme';

const { Sider } = Layout;
const { Text } = Typography;

const items = [
  { key: '/dashboard', icon: <AppstoreOutlined />, label: 'Migrations' },
  { key: '/migrations/new', icon: <PlusCircleOutlined />, label: 'New migration' },
  { key: '/operations', icon: <RobotOutlined />, label: 'Operations' },
  { key: '/monitoring', icon: <MonitorOutlined />, label: 'Drift monitoring' },
  { key: '/templates', icon: <ThunderboltOutlined />, label: 'Templates' },
  { key: '/connections', icon: <DatabaseOutlined />, label: 'Connections' },
  { key: '/settings', icon: <SettingOutlined />, label: 'Settings' },
];

export function Sidebar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const collapsed = useMigrationStore((s) => s.sidebarCollapsed);

  // Detail routes should keep "Migrations" highlighted.
  const selectedKey =
    items.find((item) => item.key === pathname)?.key ??
    (pathname.startsWith('/migrations/') ? '/dashboard' : pathname);

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      trigger={null}
      width={224}
      collapsedWidth={72}
      style={{
        borderRight: `1px solid ${brand.border}`,
        position: 'sticky',
        top: 0,
        height: '100vh',
        overflow: 'auto',
        background: 'rgba(255, 255, 255, 0.94)',
      }}
    >
      <div style={{ padding: '18px 8px 10px' }}>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={items}
          onClick={({ key }) => navigate(key)}
          style={{ borderInlineEnd: 'none', fontSize: 13.5, background: 'transparent' }}
        />
      </div>

      {!collapsed ? (
        <div style={{ padding: '12px 20px', position: 'absolute', bottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 11.5, lineHeight: 1.5 }}>
            Put your source database in read-only mode during migration to avoid drift.
          </Text>
        </div>
      ) : null}
    </Sider>
  );
}
