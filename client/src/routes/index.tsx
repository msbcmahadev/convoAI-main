import {
  BrowserRouter as Router,
  Route,
  Routes,
  Navigate,
} from "react-router-dom";
import Chatbot from "../pages/Chatbot";
import Form from "../pages/Form";
import Home from "../pages/Home";
import { Toaster } from "react-hot-toast";

export default function R() {
  return (
    <Router>
      <Routes>
        <Route path="/chatbot" element={<Chatbot />} />
        <Route path="/form" element={<Form />} />
        <Route path="/" element={<Home />} />
        <Route path="*" element={<>404, Page Not Found!</>} />
      </Routes>
      <Toaster position="bottom-right" />
    </Router>
  );
}
