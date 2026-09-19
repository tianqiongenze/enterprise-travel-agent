import type { ReactElement } from 'react';
import { Navigate } from 'react-router-dom';
import { isAuthenticated } from './auth';

export default function ProtectedRoute({ children }: { children: ReactElement }) {
  if (!isAuthenticated()) {
    return <Navigate to="/forbidden" replace />;
  }
  return children;
}
