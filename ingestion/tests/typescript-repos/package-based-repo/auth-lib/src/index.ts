export interface AuthToken {
  token: string;
  expiresAt: Date;
}

export function generateToken(): AuthToken {
  return {
    token: 'auth_' + Math.random().toString(36),
    expiresAt: new Date(Date.now() + 3600000)
  };
}