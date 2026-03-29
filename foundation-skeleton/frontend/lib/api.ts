const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export type LoginRequest = {
  email: string;
  password: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    full_name: string;
    memberships: Array<{
      tenant_id: string;
      tenant_name: string;
      tenant_slug: string;
      role: string;
    }>;
  };
};

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(`${apiBaseUrl}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    cache: 'no-store',
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(errorBody.detail ?? 'Login failed');
  }

  return response.json() as Promise<LoginResponse>;
}

export async function fetchHealth(): Promise<{ status: string; redis: string }> {
  const response = await fetch(`${apiBaseUrl}/health/ready`, { cache: 'no-store' });

  if (!response.ok) {
    throw new Error('Backend health check failed');
  }

  return response.json() as Promise<{ status: string; redis: string }>;
}
