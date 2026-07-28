import { useNavigate } from 'react-router-dom';
import { App as AntApp, Avatar, Button, Dropdown, Layout, Space, Tooltip, Typography } from 'antd';
import {
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Logo } from './Logo';
import { useAuth } from '@/hooks/useAuth';
import { useMigrationStore } from '@/store/migrationStore';
import { brand } from '@/theme';

const { Header } = Layout;
const { Text } = Typography;

export function Navbar() {
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const { user, configured, signOut } = useAuth();
  const { sidebarCollapsed, toggleSidebar } = useMigrationStore();

  const handleSignOut = async () => {
    try {
      await signOut();
      navigate('/');
    } catch {
      message.error('Could not sign out.');
    }
  };

  return (
    <Header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 20px',
        borderBottom: `1px solid ${brand.border}`,
        position: 'sticky',
        top: 0,
        zIndex: 10,
        background: 'rgba(255, 255, 255, 0.92)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
      }}
    >
      <Space size={14}>
        <Button
          type="text"
          icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={toggleSidebar}
          aria-label="Toggle navigation"
        />
        <span style={{ cursor: 'pointer' }} onClick={() => navigate('/dashboard')}>
          <Logo size={28} />
        </span>
      </Space>

      <Space size={12}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/migrations/new')}>
          New migration
        </Button>

        <Dropdown
          menu={{
            items: [
              {
                key: 'settings',
                icon: <SettingOutlined />,
                label: 'Settings',
                onClick: () => navigate('/settings'),
              },
              { type: 'divider' },
              {
                key: 'signout',
                icon: <LogoutOutlined />,
                label: 'Sign out',
                danger: true,
                disabled: !configured,
                onClick: () => void handleSignOut(),
              },
            ],
          }}
          trigger={['click']}
        >
          <Space size={8} style={{ cursor: 'pointer' }}>
            <Avatar
              size={32}
              style={{ background: brand.green100, color: brand.green700 }}
              icon={<UserOutlined />}
            />
            <Tooltip title={configured ? undefined : 'Supabase is not configured'}>
              <Text style={{ fontSize: 13, color: brand.inkSoft }}>
                {user?.email ?? 'Local session'}
              </Text>
            </Tooltip>
          </Space>
        </Dropdown>
      </Space>
    </Header>
  );
}
