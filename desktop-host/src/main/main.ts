import { app, BrowserWindow, ipcMain } from "electron";
import { join } from "node:path";
import log from "electron-log";

const isDev = process.env.NODE_ENV === "development";

const createWindow = async () => {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    backgroundColor: "#020617",
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
    },
  });

  if (isDev) {
    await win.loadURL("http://localhost:5173");
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    const indexPath = join(__dirname, "../renderer/index.html");
    await win.loadFile(indexPath);
  }
};

app.on("ready", () => {
  createWindow();

  ipcMain.handle("app:health", async () => ({
    status: "ok",
    timestamp: Date.now(),
  }));
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on("second-instance", () => {
  const [primary] = BrowserWindow.getAllWindows();
  if (primary) {
    primary.restore();
    primary.focus();
  }
});

app.on("render-process-gone", (_, details) => {
  log.error("Renderer crashed", details);
});
