// @ts-nocheck
// Test file for type extraction
import { SomeType } from '../types/SomeType';
import { AnotherType, ThirdType } from '../types/MultipleTypes';
import ts from 'typescript';

interface User {
    name: string;
    age: number;
    email: string;
}

type ProductId = string;
type Status = 'active' | 'inactive';

class UserService {
    private users: User[] = [];
    
    constructor(private config: ConfigType) {}
    
    // Function with typed parameters
    addUser(user: User, status: Status): Promise<ProductId> {
        this.users.push(user);
        return Promise.resolve('user-123');
    }
    
    // Function with imported types
    processData(data: SomeType[], metadata: AnotherType): ThirdType {
        return { processed: true, count: data.length };
    }
    
    // Function with complex types
    filterUsers(criteria: Partial<User>): User[] {
        return this.users.filter(user => {
            return Object.keys(criteria).every(key => 
                user[key as keyof User] === criteria[key as keyof User]
            );
        });
    }
    
    // Arrow function with types
    private validateUser = (user: User): boolean => {
        return user.name.length > 0 && user.age > 0;
    }
}

// Interface with type properties
interface ConfigType {
    apiUrl: string;
    timeout: number;
    retryAttempts: number;
}

// Function outside class
function createUser(name: string, age: number): User {
    return { name, age, email: '' };
}

// Function with body types for testing
function processUserWithBodyTypes(id: string): User {
    const user: User = findUser(id);
    const metadata = getUserMetadata(id) as UserMetadata;
    const config = new ConfigService<DatabaseConfig>();
    const permissions: Permissions = getPermissions(user);
    return user;
}

interface UserMetadata {
    lastLogin: Date;
    preferences: Record<string, any>;
}

interface Permissions {
    read: boolean;
    write: boolean;
    admin: boolean;
}

interface DatabaseConfig {
    host: string;
    port: number;
}

// Generic function
function processArray<T>(items: T[], processor: (item: T) => string): string[] {
    return items.map(processor);
}

// Export with types
export const defaultConfig: ConfigType = {
    apiUrl: 'https://api.example.com',
    timeout: 5000,
    retryAttempts: 3
};

export { User, ProductId, Status };
export default UserService;