import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("echoForge", {
  health: () => ipcRenderer.invoke("app:health"),
});
