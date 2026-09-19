import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { setToken } from './auth';

export default function LoginPage() {
  const [token, setTokenInput] = useState('');
  const navigate = useNavigate();

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token.trim()) {
      return;
    }
    setToken(token.trim());
    navigate('/app', { replace: true });
  };

  return (
    <div className="page">
      <header>
        <h1>Enterprise Travel Agent Login</h1>
        <p>Use production token to access protected recommendation console.</p>
      </header>
      <main className="layout single">
        <section className="panel">
          <form onSubmit={onSubmit} className="form-grid single">
            <label>
              <span>Access Token</span>
              <input
                value={token}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="paste gateway access token"
                required
              />
            </label>
            <button type="submit">Sign In</button>
          </form>
        </section>
      </main>
    </div>
  );
}
