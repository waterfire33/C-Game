'use client';

import { FormEvent, useEffect, useState } from 'react';
import { fetchHealth, login, type LoginResponse } from '../lib/api';

type HealthState = {
  status: 'loading' | 'ready' | 'error';
  message: string;
};

const defaultCredentials = {
  email: 'owner@example.com',
  password: 'changeme123',
};

export default function HomePage() {
  const [credentials, setCredentials] = useState(defaultCredentials);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loginResult, setLoginResult] = useState<LoginResponse | null>(null);
  const [health, setHealth] = useState<HealthState>({
    status: 'loading',
    message: 'Checking backend and Redis connectivity...',
  });

  useEffect(() => {
    fetchHealth()
      .then((payload) => {
        setHealth({
          status: 'ready',
          message: `${payload.status} - Redis ${payload.redis}`,
        });
      })
      .catch(() => {
        setHealth({
          status: 'error',
          message: 'Backend readiness check failed.',
        });
      });
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const payload = await login(credentials);
      setLoginResult(payload);
      setErrorMessage(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed';
      setLoginResult(null);
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <article className="panel intro">
          <p className="eyebrow">Section 1 - Foundation Skeleton</p>
          <h1>Tenant-aware product foundation.</h1>
          <p className="lead">
            Next.js handles the operator-facing login shell. FastAPI owns auth, tenant membership,
            migrations, health checks, Redis connectivity, and OpenTelemetry instrumentation.
          </p>
          <div className="metrics">
            <div className="metric">
              <strong>1 command</strong>
              <span>docker compose up --build</span>
            </div>
            <div className="metric">
              <strong>Seeded auth</strong>
              <span>Tenant, owner, and member created on boot</span>
            </div>
            <div className="metric">
              <strong>Observable</strong>
              <span>Health, logs, SQL, Redis, and request traces wired</span>
            </div>
          </div>
        </article>

        <article className="panel authCard">
          <h2>Log in</h2>
          <p>Use the seeded owner account to validate the full stack immediately after boot.</p>
          <div className={`status ${health.status === 'error' ? 'error' : 'success'}`}>
            {health.message}
          </div>
          <form onSubmit={handleSubmit}>
            <label>
              Email
              <input
                type="email"
                value={credentials.email}
                onChange={(event) =>
                  setCredentials((current) => ({ ...current, email: event.target.value }))
                }
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={credentials.password}
                onChange={(event) =>
                  setCredentials((current) => ({ ...current, password: event.target.value }))
                }
                required
              />
            </label>
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
          <p className="helper">Default credentials: owner@example.com / changeme123</p>
          {errorMessage ? <div className="status error">{errorMessage}</div> : null}
          {loginResult ? (
            <div className="status success">
              Login succeeded for {loginResult.user.full_name}. Token and tenant memberships are
              shown below.
            </div>
          ) : null}
          {loginResult ? (
            <div className="codeBlock">{JSON.stringify(loginResult, null, 2)}</div>
          ) : null}
        </article>
      </section>
    </main>
  );
}
