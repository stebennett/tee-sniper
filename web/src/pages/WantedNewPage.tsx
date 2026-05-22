import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { useCreateWanted } from '../hooks/useWanted';
import { OneShotForm } from '../components/OneShotForm';
import { RecurringForm } from '../components/RecurringForm';
import { encryptCredentials } from '../api/endpoints';

type Mode = 'one_shot' | 'recurring';

export function WantedNewPage() {
  const [mode, setMode] = useState<Mode>('one_shot');
  const [pinPrompt, setPinPrompt] = useState<{ user: string; pin: string }>({ user: '', pin: '' });
  const auth = useAuth();
  const navigate = useNavigate();
  const m = useCreateWanted();

  async function obtainBlob(): Promise<string> {
    if (auth.credentialsBlob) return auth.credentialsBlob;
    if (!auth.username) throw new Error('Not authenticated');
    if (!pinPrompt.pin) throw new Error('Re-enter PIN to save');
    const { credentials } = await encryptCredentials({
      username: auth.username, pin: pinPrompt.pin,
    });
    auth.setCredentialsBlob(credentials);
    return credentials;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async function submit(values: any) {
    try {
      const credentials = await obtainBlob();
      await m.mutateAsync({ kind: mode, body: { ...values, credentials } });
      toast.success('Wanted slot created');
      navigate('/wanted');
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail : (e as Error).message;
      toast.error(msg);
    }
  }

  return (
    <main className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-semibold mb-4">New wanted slot</h1>
      <div role="tablist" className="inline-flex bg-slate-900 rounded p-1 mb-4">
        <button role="tab" aria-selected={mode === 'one_shot'}
                onClick={() => setMode('one_shot')}
                className={`px-3 py-1 rounded ${mode === 'one_shot' ? 'bg-slate-700' : ''}`}>
          One-shot
        </button>
        <button role="tab" aria-selected={mode === 'recurring'}
                onClick={() => setMode('recurring')}
                className={`px-3 py-1 rounded ${mode === 'recurring' ? 'bg-slate-700' : ''}`}>
          Recurring
        </button>
      </div>

      {!auth.credentialsBlob && (
        <div className="mb-4 border border-amber-700/50 bg-amber-900/20 rounded p-3 text-sm">
          <p className="mb-2">Re-enter your PIN to save credentials to this slot.</p>
          <input type="password" placeholder="PIN"
                 value={pinPrompt.pin}
                 onChange={(e) => setPinPrompt({ user: auth.username ?? '', pin: e.target.value })}
                 className="bg-slate-950 border border-slate-700 rounded px-2 py-1" />
        </div>
      )}

      {mode === 'one_shot'
        ? <OneShotForm onSubmit={submit} busy={m.isPending} />
        : <RecurringForm onSubmit={submit} busy={m.isPending} />}
    </main>
  );
}
