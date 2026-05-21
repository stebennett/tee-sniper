import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useLogin } from '../hooks/useLogin';
import { loginSchema, type LoginForm } from '../lib/schemas';

export function LoginPage() {
  const navigate = useNavigate();
  const m = useLogin();
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = handleSubmit(async (values) => {
    await m.mutateAsync(values);
    navigate('/wanted');
  });

  const errorMsg =
    m.error instanceof ApiError
      ? m.error.status === 401 ? 'Invalid username or PIN.'
      : m.error.status === 502 ? 'Booking site unreachable; try again shortly.'
      : `Login failed: ${m.error.detail}`
      : null;

  return (
    <main className="min-h-screen grid place-items-center">
      <form onSubmit={onSubmit}
            className="w-full max-w-sm bg-slate-900 p-6 rounded-lg border border-slate-700 space-y-3">
        <h1 className="text-xl font-semibold">Sign in</h1>
        <label className="block text-sm">Username
          <input {...register('username')} autoComplete="username"
                 className="block w-full bg-slate-950 border border-slate-700 rounded px-2 py-1" />
          {errors.username && <p className="text-xs text-red-400">{errors.username.message}</p>}
        </label>
        <label className="block text-sm">PIN
          <input type="password" {...register('pin')} autoComplete="current-password"
                 className="block w-full bg-slate-950 border border-slate-700 rounded px-2 py-1" />
          {errors.pin && <p className="text-xs text-red-400">{errors.pin.message}</p>}
        </label>
        {errorMsg && <p className="text-sm text-red-400">{errorMsg}</p>}
        <button type="submit" disabled={m.isPending}
                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50
                           text-white rounded px-3 py-2">
          {m.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  );
}
