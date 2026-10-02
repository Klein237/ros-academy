import "./style.css";
import { readConfig } from "./config";

// « Fenêtre séparée » du bureau graphique (?vue=bureau) : une page réduite à l'écran du lab
if (readConfig(location.search).desktopOnly) void import("./bureau");
else void import("./lab");
