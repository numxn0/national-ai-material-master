import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Shell } from '@/components/layout/Shell';
import { DashboardPage } from '@/pages/DashboardPage';
import { MaterialUploadPage } from '@/pages/MaterialUploadPage';
import { MatchingReviewPage } from '@/pages/MatchingReviewPage';
import { ApprovalsAuditPage } from '@/pages/ApprovalsAuditPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/upload" element={<MaterialUploadPage />} />
          <Route path="/matching" element={<MatchingReviewPage />} />
          <Route path="/approvals" element={<ApprovalsAuditPage />} />
          <Route path="/audit" element={<ApprovalsAuditPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
};

export default App;
