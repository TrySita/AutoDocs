// A JSX component file exercised through the JavaScript parser.

// A function-declaration component returning JSX.
function Header(props) {
  return <h1>{props.title}</h1>;
}

// An arrow-function component bound to a const.
const Footer = (props) => {
  return <footer>{props.year}</footer>;
};

// A class component.
class Panel {
  render() {
    return <div>panel</div>;
  }
}
