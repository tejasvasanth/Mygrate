// import { useState } from 'react'; // used by the commented-out sign-in form
import { useNavigate } from 'react-router-dom';
import { Button, Card, Col, Row, Space, Typography } from 'antd';
// Add `App as AntApp` and `Input` back to the antd import when restoring the sign-in form.
import {
  ArrowRightOutlined,
  DatabaseOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Logo } from '@/components/layout/Logo';
import { GridBackdrop } from '@/components/ui/GridBackdrop';
import { Reveal, StaggerItem, StaggerList } from '@/components/ui/motion';
import { useAuth } from '@/hooks/useAuth';
import { brand } from '@/theme';

const { Paragraph, Text, Title } = Typography;

const FEATURES = [
  {
    icon: <DatabaseOutlined />,
    title: 'Reads your whole database',
    body: 'Schema, constraints, indexes and real data samples — across PostgreSQL, MySQL, MongoDB and SQLite.',
  },
  {
    icon: <RobotOutlined />,
    title: 'AI decides the plan',
    body: 'A five-agent pipeline understands what your data means and writes a reviewable migration plan.',
  },
  {
    icon: <ThunderboltOutlined />,
    title: 'Executes in chunks',
    body: 'Streamed batches with live progress, retries, and per-chunk logging. Memory never spikes.',
  },
  {
    icon: <SafetyCertificateOutlined />,
    title: 'Validates everything',
    body: 'Row counts, sample hashes, referential integrity — with a confidence score you can trust.',
  },
];

export function Landing() {
  const navigate = useNavigate();
  // const { message } = AntApp.useApp(); // used by the commented-out sign-in form
  const { configured, user } = useAuth();

  /* Sign-in form state — restore along with the commented form below.
  const { signInWithEmail, signUpWithEmail } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (mode: 'in' | 'up') => {
    setBusy(true);
    try {
      if (mode === 'in') await signInWithEmail(email, password);
      else await signUpWithEmail(email, password);
      navigate('/dashboard');
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'Authentication failed.');
    } finally {
      setBusy(false);
    }
  };
  */

  return (
    <div className="relative min-h-screen">
      <GridBackdrop />

      <div className="relative z-10 mx-auto max-w-[1100px] px-6 pb-20 pt-[26px]">
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Logo size={32} />
          {user || !configured ? (
            <Button type="primary" onClick={() => navigate('/dashboard')}>
              Open dashboard <ArrowRightOutlined />
            </Button>
          ) : null}
        </Space>

        <Row gutter={[48, 40]} align="middle" style={{ marginTop: 72 }}>
          <Col xs={24} md={13}>
            <Reveal>
              <Text
                style={{
                  display: 'block',
                  fontSize: 13,
                  fontWeight: 500,
                  color: brand.inkMuted,
                  letterSpacing: '0.01em',
                  marginBottom: 14,
                }}
              >
                Agentic database migration
              </Text>
              <Title
                style={{
                  fontSize: 42,
                  margin: 0,
                  letterSpacing: '-0.03em',
                  lineHeight: 1.15,
                  fontFamily: "'Satoshi', sans-serif",
                  fontWeight: 600,
                }}
              >
                Migrations take months and cost six figures.
                <span style={{ color: brand.green700 }}> We do it in hours.</span>
              </Title>
              <Paragraph style={{ fontSize: 16, color: brand.inkSoft, marginTop: 18, maxWidth: 480 }}>
                Point it at a source and a target. The agent reads your schema, profiles the
                data, reasons about what it means, and migrates it — without a DBA.
              </Paragraph>
            </Reveal>
          </Col>

          <Col xs={24} md={11}>
            <Reveal delay={0.08}>
              <Card
                variant="outlined"
                style={{ borderRadius: 10, background: brand.surface }}
                styles={{ body: { padding: 26 } }}
              >
                {/* Sign in / sign up temporarily disabled (auth guard is also
                    commented out in App.tsx). Restore by swapping this block
                    for the commented form below. */}
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Title level={4} style={{ margin: 0, fontWeight: 600 }}>
                    Get started
                  </Title>
                  <Text type="secondary" style={{ fontSize: 13.5 }}>
                    Authentication is disabled for now — jump straight into the app.
                  </Text>
                  <Button type="primary" onClick={() => navigate('/dashboard')}>
                    Continue to dashboard <ArrowRightOutlined />
                  </Button>
                </Space>
                {/*
                {configured ? (
                  <Space direction="vertical" size={14} style={{ width: '100%' }}>
                    <Title level={4} style={{ margin: 0, fontWeight: 600 }}>
                      Sign in
                    </Title>
                    <Input
                      placeholder="you@company.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                    />
                    <Input.Password
                      placeholder="Password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="current-password"
                    />
                    <Space style={{ width: '100%' }}>
                      <Button
                        type="primary"
                        loading={busy}
                        disabled={!email || !password}
                        onClick={() => void submit('in')}
                      >
                        Sign in
                      </Button>
                      <Button disabled={busy || !email || !password} onClick={() => void submit('up')}>
                        Create account
                      </Button>
                    </Space>
                  </Space>
                ) : (
                  <Space direction="vertical" size={12} style={{ width: '100%' }}>
                    <Title level={4} style={{ margin: 0, fontWeight: 600 }}>
                      Local mode
                    </Title>
                    <Text type="secondary" style={{ fontSize: 13.5 }}>
                      Supabase is not configured, so authentication is disabled. You can explore
                      the app against a local backend (or seeded demo data).
                    </Text>
                    <Button type="primary" onClick={() => navigate('/dashboard')}>
                      Continue to dashboard <ArrowRightOutlined />
                    </Button>
                  </Space>
                )}
                */}
              </Card>
            </Reveal>
          </Col>
        </Row>

        <StaggerList>
          <Row gutter={[16, 16]} style={{ marginTop: 84 }}>
            {FEATURES.map((f) => (
              <Col xs={24} sm={12} lg={6} key={f.title} style={{ display: 'flex' }}>
                <StaggerItem className="flex h-full w-full">
                  <Card
                    variant="outlined"
                    className="h-full w-full"
                    style={{ borderRadius: 10, background: brand.surface }}
                    styles={{
                      body: {
                        padding: 20,
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                      },
                    }}
                  >
                    <Space direction="vertical" size={10} style={{ width: '100%' }}>
                      <span style={{ fontSize: 20, color: brand.green700 }}>{f.icon}</span>
                      <Text strong style={{ fontSize: 14.5, fontWeight: 600 }}>
                        {f.title}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 13, lineHeight: 1.55 }}>
                        {f.body}
                      </Text>
                    </Space>
                  </Card>
                </StaggerItem>
              </Col>
            ))}
          </Row>
        </StaggerList>
      </div>
    </div>
  );
}
