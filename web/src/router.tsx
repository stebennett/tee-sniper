import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { LoginPage } from './pages/LoginPage';
import { WantedListPage } from './pages/WantedListPage';
import { WantedNewPage } from './pages/WantedNewPage';
import { WantedDetailPage } from './pages/WantedDetailPage';
import { ProtectedRoute } from './auth/ProtectedRoute';

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/wanted', element: <WantedListPage /> },
      { path: '/wanted/new', element: <WantedNewPage /> },
      { path: '/wanted/:id', element: <WantedDetailPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/wanted" replace /> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
