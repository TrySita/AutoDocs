export interface User {
  id: string;
  name: string;
}

export function createUser(name: string): User {
  return {
    id: Math.random().toString(36),
    name
  };
}