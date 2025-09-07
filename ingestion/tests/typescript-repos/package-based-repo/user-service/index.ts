// Import as npm package (package-based resolution)
import { AuthToken, generateToken } from 'auth-lib';

export interface User {
  id: string;
  name: string;
  token: AuthToken;
}

export function createAuthenticatedUser(name: string): User {
  return {
    id: Math.random().toString(36),
    name,
    token: generateToken()
  };
}