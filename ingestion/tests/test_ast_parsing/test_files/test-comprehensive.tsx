// @ts-nocheck
// Comprehensive test file for function call metadata extraction
import { readFile, writeFile } from "fs/promises";
import path, { join as pathJoin } from "path";
import { someFunction as aliasedFunction, namedImport } from "./utils/helpers";
import * as utils from "./utils/common";
import defaultImport from "./utils/default";
import { Animated, View } from "react-native";

// Export various types
export const exportedConst = 42;
export function exportedFunction() {
  return "exported";
}
export default function defaultExportFunction() {
  return "default";
}
export { namedImport as reExported };

// Local helper functions
function localHelper() {
  return "local";
}

const arrowFunction = (x: number) => x * 2;

// Class with various method types
class TestClass {
  private value = 10;

  constructor() {
    // Constructor calls
    const animated = new Animated.Value(0);
    const view = new View();
  }

  // Method with all types of calls
  async complexMethod() {
    // Local function calls
    const local = localHelper();
    const arrow = arrowFunction(5);

    // Imported function calls
    const file = await readFile("./test.txt", "utf8");
    await writeFile("./output.txt", "content");

    // Default import calls
    const defaultResult = defaultImport();

    // Named import calls
    const named = namedImport();
    const aliased = aliasedFunction();

    // Namespace calls
    const ns1 = utils.commonFunction();
    const ns2 = utils.nested.deepMethod();

    // Path utility calls (default import)
    const resolved = path.resolve("./test");
    const joined = pathJoin("/", "test");

    // Method chaining
    const chained = utils.method1().method2().method3();

    // Built-in/global calls
    console.log("test");
    JSON.parse("{}");
    Math.round(3.14);

    // Constructor calls
    const date = new Date();
    const animatedValue = new Animated.Value(100);

    // Class method calls
    this.privateMethod();

    return { local, file, defaultResult, named };
  }

  private privateMethod() {
    return this.value;
  }

  static staticMethod() {
    // Static method with calls
    const helper = localHelper();
    return helper;
  }
}

// Variable declarations with function calls
const globalVar = localHelper();
let dynamicVar = arrowFunction(10);

// Nested function
function outerFunction() {
  const outer = localHelper();

  function innerFunction() {
    // These calls should be attributed to innerFunction, not outerFunction
    const inner = localHelper();
    const nested = arrowFunction(20);
    return { inner, nested };
  }

  // This call should be attributed to outerFunction
  const innerResult = innerFunction();

  return { outer, innerResult };
}

// Async function with complex patterns
async function asyncComplexFunction() {
  try {
    // Multiple import types
    const content = await readFile("./config.json", "utf8");
    const data = JSON.parse(content);

    // Namespace with destructuring-like access
    const util1 = utils.helper.method();
    const util2 = utils.async.operation();

    // N-level nested namespace calls (edge case testing)
    const deepNested = utils.nested1.nested2.nested3.deepMethod();
    const veryDeepNested =
      utils.level1.level2.level3.level4.level5.veryDeepMethod();

    // Error handling
    console.error("Error occurred");

    return data;
  } catch (error) {
    // Error handling calls
    console.error(error);
    throw error;
  }
}

// Interface and type definitions (should not capture calls)
interface TestInterface {
  method(): void;
}

type TestType = {
  prop: string;
  func(): number;
};

// Enum
enum TestEnum {
  VALUE1 = "value1",
  VALUE2 = "value2",
}

const NewComponent = () => {
  // React component with hooks and function calls
  const [state, setState] = React.useState(0);

  const handleClick = () => {
    setState(state + 1);
    console.log("Clicked", state);
  };

  return (
    <View>
      <Text onPress={handleClick}>Click me</Text>
      <Text>{state}</Text>
    </View>
  );
};

NewComponent.functionDef = function newFunc() {
  // Function defined on component
  console.log("Function defined on component");

  return (
    <ReferencedComponent>
      <Text>Referenced Component</Text>
      <ReferencedComponent2 />
    </ReferencedComponent>
  );
};
