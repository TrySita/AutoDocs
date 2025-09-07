// @ts-nocheck
// Test file for JSX component detection in tree-sitter parser
import React from "react";
import { View, Text, TouchableOpacity, ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import CustomButton from "../components/CustomButton";
import { Header as HeaderComponent } from "../components/Header";
import * as Icons from "react-native-vector-icons";

// Export test components for reference
export const testExportedComponent = () => <View />;
export default function DefaultExportComponent() {
  return <Text>Default Export</Text>;
}

// Local helper component defined in same file
function LocalComponent({ title }: { title: string }) {
  return (
    <View>
      <Text>{title}</Text>
    </View>
  );
}

// Arrow function component
const ArrowComponent = () => {
  return <TouchableOpacity />;
};

// Main test component with various JSX patterns
export function MainTestComponent() {
  const handlePress = () => {
    console.log("Button pressed");
  };

  return (
    <SafeAreaView>
      {/* Basic imported components from react-native */}
      <ScrollView>
        <View>
          <Text>Hello World</Text>
          <TouchableOpacity onPress={handlePress}>
            <Text>Press me</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* Self-closing imported components */}
      <View />
      <Text />

      {/* Local components defined in this file */}
      <ArrowComponent />

      {/* Imported custom components */}
      <CustomButton title="Custom Button" />
      <HeaderComponent title="Header" />

      {/* Namespace/member expression components */}
      <Icons.MaterialIcon name="home" />
      <Icons.Feather name="star" />

      {/* Nested JSX */}
      <View>
        <View>
          <View>
            <Text>Deeply nested</Text>
            <LocalComponent title="Nested Local" />
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

// Class component with JSX
export class ClassTestComponent extends React.Component {
  render() {
    return (
      <View>
        <Text>Class Component</Text>
        <CustomButton title="Class Button" />
        <LocalComponent title="From Class" />
      </View>
    );
  }
}

// Component with complex JSX patterns
export function ComplexJSXComponent() {
  const items = ["item1", "item2", "item3"];

  return (
    <View>
      {items.map((item, index) => (
        <View key={index}>
          <Text>{item}</Text>
          <TouchableOpacity>
            <Icons.MaterialIcon name="delete" />
          </TouchableOpacity>
        </View>
      ))}

      {/* Conditional rendering */}
      {true && <Text>Conditional Text</Text>}
      {false ? <CustomButton title="True" /> : <CustomButton title="False" />}

      {/* Fragment */}
      <React.Fragment>
        <Text>Fragment 1</Text>
        <Text>Fragment 2</Text>
      </React.Fragment>

      {/* Short fragment syntax */}
      <>
        <LocalComponent title="Short Fragment" />
        <ArrowComponent />
      </>
    </View>
  );
}

// Hook component to test JSX in hooks context
export function HookTestComponent() {
  const [count, setCount] = React.useState(0);

  React.useEffect(() => {
    // This should not capture JSX as it's not rendered
    const unusedJSX = <Text>Not rendered</Text>;
  }, []);

  const incrementCount = () => {
    setCount(count + 1);
  };

  return (
    <View>
      <Text>Count: {count}</Text>
      <TouchableOpacity
        fakeComponent={CustomButton}
        fakeComponent2={<CustomButton2Fake />}
        fakeComponent3={
          <CustomButton3Fake>
            <Text>Fake Button</Text>
            <Text>Additional Content</Text>
            <NewComponent childComponent={NEWButton} />
          </CustomButton3Fake>
        }
        onPress={incrementCount}
      >
        <Text>Increment</Text>
      </TouchableOpacity>
      {/* <CustomButton title={`Count is ${count}`} /> */}
    </View>
  );
}
