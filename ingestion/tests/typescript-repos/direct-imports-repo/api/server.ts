import { User, createUser } from '@core';

export function handleUserRequest(name: string): User {
  return createUser(name);
}

export const routes = {
  users: '/api/users'
};