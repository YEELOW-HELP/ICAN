import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { HashRouter } from "react-router-dom";
import { store } from "./app/store";
import { AdminFeatureSwitch } from "./AdminFeatureSwitch";
import "./styles.css";
import "./console.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <HashRouter><AdminFeatureSwitch /></HashRouter>
    </Provider>
  </StrictMode>,
);
