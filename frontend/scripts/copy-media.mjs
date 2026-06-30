import { copyFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const destination = resolve(import.meta.dirname, "../dist/media");
const files = [
  "fondo.png",
  "fondoo.png",
  "fondologin.mp4",
];

await mkdir(destination, { recursive: true });
await Promise.all(
  files.map((name) => copyFile(resolve(root, name), resolve(destination, name))),
);
