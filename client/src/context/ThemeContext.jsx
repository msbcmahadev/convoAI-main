import { createContext, useState } from "react";

const ThemeContext = createContext();
const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState({
    backgroundColor: "#f9f9f9",
    textColor: "#000",
    primaryColor: "#4CAF50",
    secondaryColor: "#2A2A2A",
    errorColor: "#f44336",
  });

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export { ThemeContext, ThemeProvider };
