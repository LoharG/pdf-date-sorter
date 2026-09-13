const esbuild = require("esbuild");
const path = require("path");

esbuild
  .build({
    entryPoints: [path.join(__dirname, "src/index.ts")],
    bundle: true,
    minify: true,
    format: "iife",
    target: ["es2019"],
    outfile: path.join(__dirname, "dist/blackhole.js"),
  })
  .then(() => {
    console.log("built dist/blackhole.js");
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
