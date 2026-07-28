import { Outlet, useLocation } from 'react-router-dom';
import { Layout } from 'antd';
import { AnimatePresence } from 'framer-motion';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { PageTransition } from '@/components/ui/motion';
import { GridBackdrop } from '@/components/ui/GridBackdrop';

const { Content } = Layout;

/** Chrome shared by every authenticated page. */
export function AppLayout() {
  const location = useLocation();

  return (
    <>
      <GridBackdrop />
      <Layout style={{ minHeight: '100vh', background: 'transparent', position: 'relative', zIndex: 1 }}>
        <Sidebar />
        <Layout style={{ background: 'transparent' }}>
          <Navbar />
          <Content style={{ padding: '26px 28px 48px', background: 'transparent' }}>
            <div style={{ maxWidth: 1240, margin: '0 auto' }}>
              {/* Keyed on pathname so each route cross-fades on change. */}
              <AnimatePresence mode="wait">
                <PageTransition key={location.pathname}>
                  <Outlet />
                </PageTransition>
              </AnimatePresence>
            </div>
          </Content>
        </Layout>
      </Layout>
    </>
  );
}
