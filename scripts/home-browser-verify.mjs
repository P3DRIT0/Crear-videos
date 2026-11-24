// Verificación REAL de un piloto ya terminado; nunca registra aprobaciones.
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {readFile,writeFile} from "node:fs/promises";
import {createRequire} from "node:module";
import path from "node:path";

const root=process.env.STUDIO_HOME_ROOT || "E:/AI-Creative-Studio";
const identity=JSON.parse(await readFile(path.join(root,"logs/home-browser-production.json"),"utf8"));
const require=createRequire(import.meta.url);
const {chromium}=require(path.join(root,"tools/browser/node_modules/playwright-core"));
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe"});
const page=await browser.newPage({locale:"es-ES",viewport:{width:1280,height:820}});
const errors=[],external=[];
page.on("pageerror",error=>errors.push(String(error)));
page.on("request",r=>{if(!r.url().startsWith("http://127.0.0.1:8765/")) external.push(r.url());});
page.setDefaultTimeout(15000);
try {
  const doc=await(await page.request.get(identity.api)).json();
  assert.equal(doc.state,"ready",doc.error);
  assert.equal(doc.provider,"home-local-v1");
  assert.equal(doc.simulated,false);
  assert.deepEqual(doc.candidates.map(c=>c.length),[1,1,2,1,1]);
  assert.deepEqual(doc.reviews,[]);
  assert.equal(doc.active_review,null);
  // Fallo y latencia SIMULADOS solo en transporte del navegador; producción real intacta.
  const detailRoute=identity.api;
  let release;
  const gate=new Promise(resolve=>{release=resolve;});
  let intercepted;
  const blocked=new Promise(resolve=>{intercepted=resolve;});
  await page.route(detailRoute,async route=>{intercepted();await gate;await route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({message:"SIMULATED audit load failure"})});});
  await page.goto(identity.studio);
  await blocked;
  assert.equal(await page.locator("#workspace").evaluate(e=>e.inert),true);
  assert.equal(await page.locator("#new-production").isDisabled(),true);
  assert.equal(await page.locator("#project").isDisabled(),true);
  release();
  await page.getByRole("heading",{name:"Carga pendiente",exact:true}).waitFor();
  assert.equal(await page.locator("#new-production").isDisabled(),true);
  await page.getByRole("navigation").getByRole("link",{name:"Biblioteca",exact:true}).click();
  await page.getByRole("heading",{name:"Carga pendiente",exact:true}).waitFor();
  await page.evaluate(()=>{location.hash="story";});
  await page.unroute(detailRoute);
  await page.getByRole("button",{name:"Reintentar carga",exact:true}).click();
  await page.getByRole("heading",{name:"Guion HOME · Ollama",exact:true}).waitFor();
  assert.equal(await page.locator("#workspace").evaluate(e=>e.inert),false);
  assert.equal(await page.locator("#new-production").isDisabled(),false);
  await page.getByRole("navigation").getByRole("link",{name:"Montaje",exact:true}).click();
  await page.getByRole("heading",{name:"Reel HOME · IA local",exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector("video.work-video")?.readyState>=1);
  const media=await page.locator("video.work-video").first().evaluate(v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight}));
  assert.equal(media.duration,15);
  assert.equal(media.width,1080);
  assert.equal(media.height,1920);
  const downloaded=page.waitForEvent("download");
  await page.getByRole("link",{name:"Manifest",exact:true}).click();
  const download=await downloaded;
  const data=await readFile(await download.path());
  assert.equal(createHash("sha256").update(data).digest("hex"),doc.output.assets.manifest.sha256);
  const manifest=JSON.parse(data);
  assert.equal(manifest.simulated,false);
  assert.equal(manifest.human_review,"pending");
  assert.equal(manifest.qc.passed,true);
  assert.equal(manifest.models.length,5);
  assert.ok(manifest.models.every(m=>m.license_asset));
  assert.ok(Object.values(manifest.outputs).every(a=>a.simulated===false && a.license_verified));
  await page.screenshot({path:path.join(root,"logs/home-dashboard-final.png"),fullPage:true});
  await page.getByRole("navigation").getByRole("link",{name:"Biblioteca",exact:true}).click();
  assert.equal(await page.getByRole("link",{name:"Descargar licencia",exact:true}).count(),5);
  assert.deepEqual(errors,[]);
  assert.deepEqual(external,[]);
  await writeFile(path.join(root,"logs/home-browser-verified.json"),JSON.stringify({
    production:doc.id,video_sha256:doc.output.assets.video.sha256,manifest_sha256:doc.output.assets.manifest.sha256,
    qc:manifest.qc,media,models:manifest.models.length,errors,external_requests:external,review:"pending",publishing:false
  },null,2));
  console.log("OK · HOME real en navegador: montaje, reproducción, manifest/hash, cinco licencias, cero peticiones externas y cero aprobaciones.");
} finally {await browser.close();}
