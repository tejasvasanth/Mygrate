import { App as AntApp, ConfigProvider } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
// Auth guard temporarily disabled — re-enable by restoring this import and the
// <RequireAuth> wrapper around AppLayout below.
// import { RequireAuth } from '@/components/layout/RequireAuth';
import { Connections } from '@/pages/Connections';
import { Dashboard } from '@/pages/Dashboard';
import { Landing } from '@/pages/Landing';
import { MigrationDetail } from '@/pages/MigrationDetail';
import { Monitoring } from '@/pages/Monitoring';
import { NewMigration } from '@/pages/NewMigration';
import { Operations } from '@/pages/Operations';
import { PublicReport } from '@/pages/PublicReport';
import { Settings } from '@/pages/Settings';
import { Templates } from '@/pages/Templates';
import { antdTheme } from '@/theme';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={antdTheme}>
        <AntApp>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Landing />} />
              {/* <RequireAuth> wrapper removed for now — see comment on the import above. */}
              <Route element={<AppLayout />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/migrations/new" element={<NewMigration />} />
                <Route path="/migrations/:id" element={<MigrationDetail />} />
                <Route path="/operations" element={<Operations />} />
                <Route path="/monitoring" element={<Monitoring />} />
                <Route path="/templates" element={<Templates />} />
                <Route path="/connections" element={<Connections />} />
                <Route path="/settings" element={<Settings />} />
                {/* Shared report — public, but rendered inside the shell so
                    visitors can navigate into the product from it. */}
                <Route path="/r/:token" element={<PublicReport />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
