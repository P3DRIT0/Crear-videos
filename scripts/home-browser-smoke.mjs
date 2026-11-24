// Prueba REAL opt-in: crea un piloto local sin aprobarlo ni publicarlo.
import assert from "node:assert/strict";
import {createRequire} from "node:module";
import {writeFile} from "node:fs/promises";
import path from "node:path";

const root = process.env.STUDIO_HOME_ROOT || "E:/AI-Creative-Studio";
const require = createRequire(import.meta.url);
const {chromium} = require(path.join(root, "tools/browser/node_modules/playwright-core"));
const browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe"});
const origin="http://127.0.0.1:8765";
const brand="720c761b-64d9-4d3c-9dd5-b1dc2e82edeb";
const page=await browser.newPage({locale:"es-ES"});
page.setDefaultTimeout(12000);
try {
  await page.goto(origin);
  await page.locator("#brand option[value='"+brand+"']").waitFor({state:"attached"});
  await Promise.all([
    page.waitForResponse(r=>r.url().endsWith("/brands/"+brand+"/campaigns")),
    page.locator("#brand").selectOption(brand)
  ]);
  await page.getByRole("button",{name:"Nueva campaña",exact:true}).click();
  const name="Retrobay · Integración HOME " + Date.now();
  await page.getByRole("dialog").getByLabel("Nombre",{exact:true}).fill(name);
  await page.getByRole("dialog").getByLabel("Objetivo",{exact:true}).fill("Lumen, un pequeño robot original con visor ámbar y cuerpo de cobre, descubre una luz en un arcade y despierta una consola. Cinco planos con movimientos suaves, sin textos ni personajes ajenos.");
  await page.getByRole("button",{name:"Guardar",exact:true}).click();
  await page.getByRole("dialog").waitFor({state:"hidden"});
  const campaigns=await (await page.request.get(origin+"/api/v1/brands/"+brand+"/campaigns")).json();
  const campaign=campaigns.find(c=>c.name===name);
  assert.ok(campaign);
  await page.goto(origin+"/studio?brand="+brand+"&campaign="+campaign.id);
  await page.getByRole("button",{name:"Nueva producción",exact:true}).click();
  await page.locator("select[name=provider]").selectOption("home-local-v1");
  await page.locator("select[name=preset]").selectOption("cinematic");
  const response=page.waitForResponse(r=>r.url().endsWith("/productions") && r.request().method()==="POST");
  await page.getByRole("button",{name:"Guardar",exact:true}).click();
  const created=await (await response).json();
  await page.getByRole("dialog").waitFor({state:"hidden"});
  await page.waitForURL(url=>url.pathname==="/studio" && url.searchParams.get("production")===created.id);
  const production=new URL(page.url()).searchParams.get("production");
  assert.ok(production);
  const api=origin+"/api/v1/brands/"+brand+"/productions/"+production;
  const saved={brand,production,campaign:campaign.id,api,studio:origin+"/studio?brand="+brand+"&production="+production};
  await writeFile(path.join(root,"logs/home-browser-production.json"),JSON.stringify(saved,null,2));
  await page.getByRole("button",{name:"Renderizar reel",exact:true}).click();
  const deadline=Date.now()+600000;
  let observed=false;
  while(Date.now()<deadline) {
    const doc=await (await page.request.get(api)).json();
    if(doc.state==="failed") throw Error(doc.error);
    const op=doc.home.operations.at(-1);
    if(op?.kind==="clip" && op.state==="running") {
      assert.equal(doc.home.reference_ready,true);
      await writeFile(path.join(root,"logs/home-before-restart.json"),JSON.stringify(doc,null,2));
      console.log(JSON.stringify({...saved,active_provider_id:op.id,selected:doc.selected}));
      observed=true;
      break;
    }
    await new Promise(r=>setTimeout(r,1000));
  }
  assert.equal(observed,true,"No se observó un clip real activo antes del plazo.");
} catch (error) {
  console.error(await page.locator("body").innerText());
  throw error;
} finally {await browser.close();}
