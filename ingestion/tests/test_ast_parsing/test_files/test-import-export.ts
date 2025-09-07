// @ts-nocheck
import defaultExport from "module-name-1";
import * as name from "module-name-2";
import { export1 } from "module-name-3";
import { export1 as alias1 } from "module-name-4";
import { default as alias } from "module-name-5";
import { export1, export2 } from "module-name-6";
import { export1, export2 as alias2, /* … */ } from "module-name-7";
import { "string name" as alias } from "module-name-8";
import defaultExport2, { export1 as alias, export2, /* … */ } from "module-name-9";
import defaultExport3, * as name from "module-name-10";

const requireImport = require("require-module");

/**
 * This is a test function with JSDoc
 * @param name - The name parameter
 * @returns A greeting string
 */
export async function greet(name: string): Promise<string> {
    const a = await import("module-name-12");
    return `Hello, ${name}!`;
}

/**
 * A test class with documentation
 */
export class TestClass {
    /**
     * Constructor for TestClass
     * @param value - Initial value
     */
    constructor(private value: number) { }

    /**
     * Get the current value
     * @returns The current value
     */
    getValue(): number {
        return this.value;
    }
}

/**
 * A test const with data
 */
export const MICRO_NUTRIENTS = [
    { name: "saturated_fat", unit: "g" },
    { name: "polyunsaturated_fat", unit: "g" },
    { name: "monounsaturated_fat", unit: "g" },
    { name: "trans_fat", unit: "g" },
    { name: "cholesterol", unit: "mg" },
    { name: "sodium", unit: "mg" },
    { name: "potassium", unit: "mg" },
    { name: "fiber", unit: "g" },
    { name: "sugar", unit: "g" },
    { name: "added_sugars", unit: "g" },
    { name: "vitamin_d", unit: "mcg" },
    { name: "vitamin_a", unit: "mcg" },
    { name: "vitamin_c", unit: "mg" },
    { name: "calcium", unit: "mg" },
    { name: "iron", unit: "mg" },
];

/**
 * A test interface
 */
export interface TestInterface {
    name: string;
    age: number;
}

/**
 * A test type alias
 */
export type TestType = string | number;

/**
 * A test enum
 */
export enum TestEnum {
    VALUE1 = 'value1',
    VALUE2 = 'value2'
}

// Additional import patterns for comprehensive testing
const path = require('path'); // CommonJS require

// Additional export patterns
export const exportedConst = "constant value";
export let exportedLet = "mutable value";
export var exportedVar = "var value";

// Export default variations (only one default export allowed per module)
const defaultValue = 42;
export default defaultValue;

// Re-export patterns
export { greet as renamedGreet } from "./some-module";
export { TestClass as RenamedClass };
export * from "./another-module";

// Complex export patterns
export {
    exportedConst as ExportedConst,
    exportedLet as ExportedLet,
    exportedVar as ExportedVar
};