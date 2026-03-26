import { useState } from 'react';
import { Card } from '../shared/ui/Card';
import { api } from '../lib/api';

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState('');
  const [status, setStatus] = useState<'idle' | 'validating' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const hasKey = !!localStorage.getItem('quant-api-key');

  const save = async () => {
    if (!apiKey.trim()) return;
    setStatus('validating');
    setErrorMsg('');
    localStorage.setItem('quant-api-key', apiKey.trim());
    try {
      await api.health();
      setStatus('success');
      setApiKey('');
    } catch (err) {
      setStatus('error');
      setErrorMsg(err instanceof Error ? err.message : '驗證失敗');
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-white">設定</h1>
      <Card>
        <h2 className="text-base font-semibold text-white mb-2">API Key</h2>
        <p className="text-xs text-neutral-500 mb-4">
          {hasKey ? 'API Key 已設定' : 'API Key 尚未設定'}
        </p>
        <div className="flex gap-3">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => { setApiKey(e.target.value); setStatus('idle'); }}
            placeholder="輸入新的 API Key"
            className="flex-1 rounded-md border border-white/15 bg-[#262626] px-3 py-2 text-sm text-white placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          />
          <button
            onClick={save}
            disabled={status === 'validating' || !apiKey.trim()}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors duration-150 disabled:opacity-50"
          >
            {status === 'validating' ? '驗證中...' : '儲存'}
          </button>
        </div>
        {status === 'success' && (
          <p className="text-sm text-emerald-400 mt-3">API Key 驗證成功，已儲存。</p>
        )}
        {status === 'error' && (
          <p className="text-sm text-red-400 mt-3">驗證失敗：{errorMsg}</p>
        )}
      </Card>
    </div>
  );
}
