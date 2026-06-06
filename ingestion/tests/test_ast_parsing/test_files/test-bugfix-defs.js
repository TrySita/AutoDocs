// Plain JavaScript definitions covering each capture kind.

// A named function declaration.
function greet(name) {
  return `hello ${name}`;
}

// An arrow function bound to a const.
const add = (a, b) => a + b;

// A function expression bound to a let.
let multiply = function (a, b) {
  return a * b;
};

// A class with a method.
class Calculator {
  square(x) {
    return x * x;
  }
}

// A plain constant (non-function value).
const PI = 3.14159;

// An exported arrow function.
export const subtract = (a, b) => a - b;

// Assignment of a function to an identifier.
let handler;
handler = function () {
  return 42;
};
