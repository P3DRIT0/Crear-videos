// Prueba de navegador opcional. Usa la instalación local de Playwright y su caché.
import assert from "node:assert/strict";
import {studioFlow} from "./studio-flow.mjs";
import {spawn, spawnSync} from "node:child_process";
import {createHash} from "node:crypto";
import {mkdtemp, readdir, readFile, rm} from "node:fs/promises";
import {homedir, tmpdir} from "node:os";
import path from "node:path";
import {once} from "node:events";
import {createRequire} from "node:module";
import {createInterface} from "node:readline";
import {fileURLToPath} from "node:url";

const require = createRequire(import.meta.url);
const root = fileURLToPath(new URL("../", import.meta.url));
async function playwright() {
  if (process.env.PLAYWRIGHT_CORE) return require(path.resolve(process.env.PLAYWRIGHT_CORE));
  try { return require("playwright-core"); } catch (err) {
    if (err.code !== "MODULE_NOT_FOUND") throw err;
  }
  const cache = process.env.PLAYWRIGHT_BROWSERS_PATH || path.join(homedir(), ".cache/ms-playwright");
  const registry = path.join(cache, ".links");
  for (const link of await readdir(registry).catch(() => [])) {
    const installed = (await readFile(path.join(registry,link),"utf8")).trim();
    if (path.basename(installed) !== "playwright-core") continue;
    try { return require(installed); } catch (err) { if (err.code !== "MODULE_NOT_FOUND") throw err; }
  }
  throw Error("Falta playwright-core local. Indique PLAYWRIGHT_CORE o ejecute scripts/test para probar la API.");
}

const {chromium} = await playwright();
const data = await mkdtemp(path.join(tmpdir(),"studio-ui-"));
const server = spawn(process.env.STUDIO_PYTHON || "python3", ["-u","-c", [
  "from apps.api.server import build_server, Config",
  "from apps.api.worker import loop",
  "from threading import Thread, Event",
  "with build_server(Config.load(), port=0) as server:",
  " Thread(target=loop,args=(server.studio,Event()),daemon=True).start()",
  " print(server.server_port, flush=True)",
  " server.serve_forever()"
].join("\n")], {cwd:root,env:{...process.env,STUDIO_DATA:data,STUDIO_DB:"sqlite",STUDIO_PROFILE:"work",STUDIO_ENABLE_HOME:"0"},
  stdio:["ignore","pipe","inherit"]});
const stopped = once(server,"exit");
let browser;
try {
  const lines = createInterface({input:server.stdout});
  const port = await Promise.race([once(lines,"line").then(([line]) => Number(line)),
    stopped.then(() => {throw Error("El servidor de prueba no ha arrancado.");})]);
  assert.ok(Number.isInteger(port) && port > 0);
  const origin = "http://127.0.0.1:" + port;
  browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH});
  const page = await browser.newPage({locale:"es-ES", viewport:{width:1280,height:820}});
  page.setDefaultTimeout(6000);
  const errors = [], outside = [];
  page.on("pageerror", e=>errors.push(String(e)));
  await page.route("**/*", route=>{
    if (new URL(route.request().url()).origin === origin) return route.continue();
    outside.push(route.request().url());
    return route.abort();
  });
  await page.goto(origin);
  const button = name=>page.getByRole("button",{name,exact:true});
  const nav = name=>page.getByRole("navigation").getByRole("link",{name});
  await button("Nueva campaña").click();
  await page.getByLabel("Nombre",{exact:true}).fill("Colección de otoño");
  await page.getByLabel("Objetivo").fill("Presentar los diseños propios.");
  await button("Guardar").click();
  await page.getByRole("heading",{name:"Colección de otoño"}).waitFor();
  await nav("Campañas").click();
  await button("Editar").click();
  await page.getByLabel("Nombre",{exact:true}).fill("Retrobay <otoño>");
  await button("Guardar").click();
  await page.getByRole("heading",{name:"Retrobay <otoño>"}).waitFor();
  await button("Crear job").click();
  await button("Guardar").click();
  await page.getByRole("dialog").waitFor({state:"hidden"});
  await button("Eliminar").click();
  await page.getByRole("dialog").getByRole("button",{name:"Eliminar",exact:true}).click();
  await page.getByRole("alert").filter({hasText:"Elimine primero los jobs"}).waitFor();
  await button("Cancelar").click();
  await nav("Jobs").click();
  await button("Editar").click();
  await page.getByLabel("Nombre del job").fill("Ficha final");
  await button("Guardar").click();
  await page.getByRole("heading",{name:"Ficha final"}).waitFor();
  await button("Ejecutar").click();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("link",{name:"Descargar ficha"}).click();
  const download = await downloadEvent;
  const bytes = await readFile(await download.path());
  assert.equal(JSON.parse(bytes).campaign.name,"Retrobay <otoño>");
  await page.getByText(createHash("sha256").update(bytes).digest("hex"),{exact:false}).waitFor();
  await page.reload();
  await page.getByText("Completado",{exact:true}).waitFor();
  await page.setViewportSize({width:375,height:800});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth));
  await nav("Sistema").click();
  await page.getByText("sqlite",{exact:true}).waitFor();
  await nav("Jobs").click();
  await button("Eliminar").click();
  await page.getByRole("dialog").getByRole("button",{name:"Eliminar",exact:true}).click();
  await page.getByText("Crea un job desde una campaña",{exact:false}).waitFor();
  await nav("Campañas").click();
  await button("Eliminar").click();
  await page.getByRole("dialog").getByRole("button",{name:"Eliminar",exact:true}).click();
  await page.getByText("Todavía no hay campañas.").waitFor();
  await studioFlow(page,origin);
  assert.deepEqual(errors,[]);
  assert.deepEqual(outside,[]);
  console.log("OK · Chromium " + browser.version() + " · CRUD, montaje, revisión de fixture, calendario dry-run, móvil y cero peticiones externas del dashboard.");
} finally {
  try { await browser?.close(); } finally {
    // El lanzador de venv Windows deja un intérprete hijo: cerrar todo el árbol propio.
    if(process.platform==="win32" && server.exitCode===null) {
      const cleanup=spawnSync("taskkill.exe",["/PID",String(server.pid),"/T","/F"],{windowsHide:true,stdio:"ignore"});
      if(cleanup.error || cleanup.status!==0) throw Error("No se pudo cerrar el servidor aislado del test.");
    } else server.kill();
    await stopped;
    await rm(data,{recursive:true,force:true});
  }
}
