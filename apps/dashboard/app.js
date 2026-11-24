"use strict";
const $ = (selector) => document.querySelector(selector);
const escapeText = (value) => String(value).replace(/[&<>"']/g, (c) =>
  ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[c]);
const pages = {resumen:"Resumen", campanas:"Campañas", jobs:"Jobs", sistema:"Sistema"};
const states = {pending:"Pendiente", succeeded:"Completado", failed:"Fallido"};
const dateFormat = new Intl.DateTimeFormat("es-ES", {timeZone:"Europe/Madrid", dateStyle:"short", timeStyle:"short"});
const view = $("#view");
const dialog = $("#dialog");
let brands = [], campaigns = [], jobs = [], sequence = 0, activeForm;
const base = () => "/brands/" + $("#brand").value;
const notice = (message) => { $("#notice").textContent = message; };

async function api(path, method = "GET", body, key) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (key) headers["Idempotency-Key"] = key;
  const response = await fetch("/api/v1" + path, {method, headers, body:body && JSON.stringify(body)});
  if (response.status === 204) return;
  const result = await response.json();
  if (!response.ok) throw new Error(result.message || "El estudio no ha podido completar la operación.");
  return result;
}
function button(action, label, id = "", css = "") {
  return '<button type="button" class="' + css + '" data-action="' + action + '" data-id="' + id + '">' + label + '</button>';
}
function panel(title, content, link = "") {
  return '<section class="panel"><div class="panel-head"><h2>' + title + '</h2>' + link + '</div>' + content + '</section>';
}
function campaignRow(c) {
  const count = jobs.filter(j => j.campaign_id === c.id).length;
  return '<article class="row"><div><h3>' + escapeText(c.name) + '</h3><p class="desc">' + escapeText(c.objective) +
    '</p><span class="meta">' + dateFormat.format(new Date(c.created_at)) + ' · ' + count + ' jobs</span></div><div class="actions">' +
    '<a class="button" href="/studio?brand='+c.brand_id+'&campaign='+c.id+'">Abrir estudio</a>' + button("new-job","Crear job",c.id) + button("edit-campaign","Editar",c.id) + button("delete-campaign","Eliminar",c.id,"danger") + '</div></article>';
}
function jobRow(j) {
  const campaign = campaigns.find(c => c.id === j.campaign_id);
  let actions = "";
  if (j.state === "pending") actions += button("edit-job","Editar",j.id);
  if (j.state === "succeeded") {
    actions += '<a class="button" download="ficha-' + j.id + '.json" href="/api/v1' + base() + '/jobs/' + j.id + '/artifact">Descargar ficha</a>';
  } else {
    actions += button("run", j.state === "failed" ? "Reintentar" : "Ejecutar", j.id, "primary");
  }
  return '<article class="row"><div><h3>' + escapeText(j.label) + '</h3><p class="desc">' + escapeText(campaign?.name || "") +
    '</p><span class="tag ' + j.state + '">' + states[j.state] + '</span> <span class="meta">' +
    dateFormat.format(new Date(j.created_at)) + '</span>' + (j.error ? '<p>' + escapeText(j.error) + '</p>' : '') +
    (j.sha256 ? '<p class="meta">SHA-256 · ' + j.sha256 + '</p>' : '') + '</div><div class="actions">' +
    actions + button("delete-job","Eliminar",j.id,"danger") + '</div></article>';
}
function rows(items, format, empty) {
  return items.map(format).join("") || '<p class="empty">' + empty + '</p>';
}
function hero(title, detail, action = "") {
  return '<div class="hero"><div><h1>' + title + '</h1><p>' + detail + '</p></div>' + action + '</div>';
}
function summary() {
  const stats = [["Campañas", campaigns.length], ["Jobs pendientes", jobs.filter(j=>j.state==="pending").length],
    ["Fichas listas", jobs.filter(j=>j.state==="succeeded").length]];
  return hero("Resumen", "Actividad de " + escapeText($("#brand").selectedOptions[0].textContent) + ".",
    button("new-campaign","Nueva campaña","","primary")) +
    '<div class="stats">' + stats.map(([label, number]) => '<div class="stat"><span class="micro">' + label +
    '</span><strong>' + number + '</strong></div>').join("") + '</div>' +
    panel("Campañas recientes", rows(campaigns.slice(0,3),campaignRow,"Crea una campaña para definir su objetivo."),
      '<a class="link" href="#campanas">Ver campañas</a>') +
    panel("Últimos jobs", rows(jobs.slice(0,3),jobRow,"Los jobs de ficha aparecerán aquí al crearlos."),
      '<a class="link" href="#jobs">Ver jobs</a>');
}
async function refresh() {
  const request = ++sequence;
  view.setAttribute("aria-busy","true");
  const page = Object.hasOwn(pages,location.hash.slice(1)) ? location.hash.slice(1) : "resumen";
  document.title = pages[page] + " · Creative Studio";
  for (const a of document.querySelectorAll("nav a")) {
    if (a.hash === "#" + page) a.setAttribute("aria-current","page");
    else a.removeAttribute("aria-current");
  }
  try {
    if (!brands.length) {
      const found = await api("/brands");
      if (request !== sequence) return;
      brands = found;
      $("#brand").replaceChildren(...brands.map(b => new Option(b.name,b.id)));
      const capabilities = await api("/system/capabilities");
      $(".environment").textContent = capabilities.home_enabled ? "HOME / Local" : "WORK / Local";
    }
    $(".brand-icon").textContent = $("#brand").selectedOptions[0].textContent.slice(0,1);
    if (page === "sistema") {
      const [health, cap] = await Promise.all([api("/health"),api("/system/capabilities")]);
      if (request !== sequence) return;
      const info = [["Perfil",cap.profile.toUpperCase()],["Base de datos",health.database],["Migración",health.schema_version],
        ["Almacenamiento","Lectura de esquema y escritura de prueba correctas"],["Ejecutor","Manual · síncrono"],
        ["Jobs GPU",cap.gpu_jobs],["Inferencia remota","Desactivada"],["Publicación","Desactivada"]];
      view.innerHTML = hero("Sistema","Recursos del proceso local.") + panel("Estado de " + cap.profile.toUpperCase(),'<dl>' +
        info.map(([k,v])=>'<dt>'+k+'</dt><dd>'+escapeText(v)+'</dd>').join("")+'</dl>',
        '<a class="link" href="/api/v1/openapi.json">OpenAPI</a>');
    } else {
      const [cs, js] = await Promise.all([api(base()+"/campaigns"), api(base()+"/jobs")]);
      if (request !== sequence) return;
      campaigns = cs;
      jobs = js;
      if (page === "resumen") view.innerHTML = summary();
      if (page === "campanas") view.innerHTML = hero("Campañas","Objetivos de producción de la marca.",
        button("new-campaign","Nueva campaña","","primary")) + panel("Todas las campañas",rows(cs,campaignRow,"Todavía no hay campañas."));
      if (page === "jobs") view.innerHTML = hero("Jobs","Cada job guarda una ficha JSON de su campaña.",
        cs.length ? button("new-job","Nuevo job","","primary") : button("new-campaign","Nueva campaña","","primary")) +
        panel("Registro de ejecución",rows(js,jobRow,"Crea un job desde una campaña para guardar su ficha."));
    }
  } catch (err) {
    if (request !== sequence) return;
    view.innerHTML = hero("Estudio no disponible",escapeText(err.message),button("refresh","Reintentar"));
  } finally {
    if (request === sequence) view.setAttribute("aria-busy","false");
  }
}
function openEditor(action, id) {
  const campaign = campaigns.find(c=>c.id===id);
  const job = jobs.find(j=>j.id===id);
  const isCampaign = action.endsWith("campaign");
  const collection = isCampaign ? "campaigns" : "jobs";
  const editing = action.startsWith("edit");
  const deleting = action.startsWith("delete");
  const entity = isCampaign ? campaign : job;
  const title = deleting ? (isCampaign ? "Eliminar campaña" : "Eliminar job") :
    (isCampaign ? (editing ? "Editar campaña" : "Nueva campaña") : (editing ? "Editar job" : "Nuevo job"));
  $("#dialog-title").textContent = title;
  $("#submit").textContent = deleting ? "Eliminar" : "Guardar";
  $("#form-error").textContent = "";
  let fields;
  if (deleting) fields = '<p>Se eliminará «' + escapeText(entity.name || entity.label) + '» del registro local.</p>';
  else if (isCampaign) fields = '<label class="field">Nombre<input name="name" maxlength="100" required></label>' +
    '<label class="field">Objetivo<textarea name="objective" maxlength="1000" required></textarea></label>';
  else fields = (editing ? '' : '<label class="field">Campaña<select name="campaign_id">' +
    campaigns.map(c=>'<option value="'+c.id+'">'+escapeText(c.name)+'</option>').join("") + '</select></label>') +
    '<label class="field">Nombre del job<input name="label" maxlength="100" required></label>';
  $("#fields").innerHTML = fields;
  const elements = $("#editor").elements;
  if (editing) for (const k of (isCampaign ? ["name","objective"] : ["label"])) elements[k].value = entity[k];
  if (action === "new-job") {
    if (campaign) elements.campaign_id.value = campaign.id;
    elements.label.value = "Ficha de campaña";
  }
  activeForm = {path:base()+"/"+collection + (editing || deleting ? "/"+id : ""),
    method:deleting ? "DELETE" : editing ? "PATCH" : "POST", key:crypto.randomUUID()};
  dialog.showModal();
  ($("#fields input, #fields textarea, #fields select") || $("#cancel")).focus();
}
view.addEventListener("click",async event => {
  const control = event.target.closest("button[data-action]");
  if (!control) return;
  notice("");
  const {action,id} = control.dataset;
  if (action === "refresh") return refresh();
  if (action !== "run") return openEditor(action,id);
  control.disabled = true;
  try {
    const job = await api(base()+"/jobs/"+id+"/run","POST");
    await refresh();
    notice(job.error || "Ficha guardada. Ya puedes descargarla.");
  } catch (err) { notice(err.message); control.disabled = false; }
});
$("#editor").addEventListener("submit",async event => {
  event.preventDefault();
  const {path,method,key} = activeForm;
  for (const control of dialog.querySelectorAll("button")) control.disabled = true;
  try {
    const body = method === "DELETE" ? undefined : Object.fromEntries(new FormData(event.currentTarget));
    await api(path,method,body,method === "POST" ? key : undefined);
    dialog.close();
    await refresh();
    notice(method === "DELETE" ? "Registro eliminado." : "Cambios guardados.");
  } catch (err) { $("#form-error").textContent = err.message; }
  finally { for (const control of dialog.querySelectorAll("button")) control.disabled = false; }
});
dialog.addEventListener("cancel", event => { if ($("#submit").disabled) event.preventDefault(); });
for (const id of ["#cancel","#close"]) $(id).onclick = () => dialog.close();
$("#brand").onchange = () => { notice(""); refresh(); };
window.addEventListener("hashchange", () => { notice(""); refresh(); });
refresh();
