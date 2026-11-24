"use strict";
const $ = s => document.querySelector(s);
const esc = value =>
    String(value ?? "")
        .replace(
            /[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"})[c]);
const params = new URLSearchParams(location.search);
const names = {
  draft: "Borrador",
  queued: "En cola",
  rendering: "Renderizando",
  ready: "Listo para revisar",
  cancelled: "Cancelado",
  failed: "Fallido",
  scheduled: "Programado",
  dry_run: "Simulación completada"
};
let brand = params.get("brand"), project = params.get("production"), campaign = params.get("campaign");
let campaigns = [], characters = [], projects = [], registry = {}, publications = [], metrics = {},
    policy = {}, doc = null, source = null, generation = 0, loaded = false, submitForm;
const base = () => "/brands/" + brand;
const prod = () => base() + "/productions/" + project;
const tab = () => ["edit", "review", "calendar", "library"].includes(location.hash.slice(1)) ?
    location.hash.slice(1) :
    "story";
const date = t =>
    new Intl.DateTimeFormat("es-ES", {timeZone: "Europe/Madrid", dateStyle: "short", timeStyle: "short"})
        .format(new Date(t));
const say = t => {
  $("#feedback").textContent = t;
};
const unconfirmed = new Map();
async function api(path, method = "GET", body, key) {
  const headers = {};
  const signature = JSON.stringify([path, body]);
  if (method === "POST") {
    headers["Idempotency-Key"] = key || unconfirmed.get(signature) || crypto.randomUUID();
    unconfirmed.set(signature, headers["Idempotency-Key"]);
  }
  if (body)
    headers["Content-Type"] = "application/json";
  const r = await fetch("/api/v1" + path, {method, headers, body: body ? JSON.stringify(body) : undefined});
  const data = await r.json();
  if (method === "POST" && (r.ok || r.status < 500)) unconfirmed.delete(signature);
  if (!r.ok) throw Error(data.message || "Error local");
  return data;
}
const btn = (action, label, extra = "") =>
    "<button type=\"button\" data-do=\"" + action + "\" " + extra + ">" + esc(label) + "</button>";
const panel = (title, body) => "<section class=\"panel\"><div class=\"panel-head\"><h2>" + esc(title) +
    "</h2></div>" + body + "</section>";
const field = (label, input) => "<label class=\"field\">" + label + input + "</label>";
const input = (name, value = "", max = 100) =>
    "<input required maxlength=\"" + max + "\" name=\"" + name + "\" value=\"" + esc(value) + "\">";
const area = (name, value = "", max = 1000) =>
    "<textarea required name=\"" + name + "\" maxlength=\"" + max + "\">" + esc(value) + "</textarea>";
const options = (rows, key, label) =>
    rows.map(r => "<option value=\"" + esc(r[key]) + "\">" + esc(r[label]) + "</option>").join("");
const url = hash => "/api/v1" + prod() + "/assets/" + hash;
const video = (hash, css = "work-video") =>
    "<video class=\"" + css + "\" controls preload=\"metadata\" src=\"" + url(hash) + "\"></video>";
function dialog(title, html, handler) {
  $("#heading").textContent = title;
  $("#inputs").innerHTML = html;
  $("#failure").textContent = "";
  submitForm = handler;
  $("#modal").showModal();
  $("#inputs input, #inputs select, #inputs textarea")?.focus();
}
$("#dismiss").onclick = () => $("#modal").close();
$("#form").onsubmit = async e => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.currentTarget));
  $("#submit").disabled = true;
  $("#dismiss").disabled = true;
  try {
    await submitForm(data);
    $("#modal").close();
    await load();
    say("Cambios guardados.");
  } catch (err) {
    $("#failure").textContent = err.message;
  } finally {
    $("#submit").disabled = false;
    $("#dismiss").disabled = false;
  }
};
$("#modal").oncancel = e => {
  if ($("#submit").disabled)
    e.preventDefault();
};
function disconnect() {
  source?.close();
  source = null;
}
function connect() {
  disconnect();
  if (!doc || !["queued", "rendering"].includes(doc.state))
    return;
  const id = project, revision = doc.revision;
  source = new EventSource("/api/v1" + prod() + "/events?after=" + revision);
  source.onmessage = event => {
    if (project === id && Number(event.lastEventId) > revision) {
      disconnect();
      load().catch(e => say(e.message));
    }
  };
}
async function load() {
  const seq = ++generation;
  let valid=false;
  loaded=false;
  disconnect();
  setBusy(true);
  try {
  const all = await api("/brands");
  if (seq !== generation)
    return;
  if (!all.some(b => b.id === brand))
    brand = all[0].id;
  $("#brand").innerHTML = options(all, "id", "name");
  $("#brand").value = brand;
  const results = await Promise.all([
    "campaigns", "characters", "productions", "registry", "publications", "metrics", "policy"
  ].map(c => api(base() + "/" + c)));
  if (seq !== generation)
    return;
  [campaigns, characters, projects, registry, publications, metrics, policy] = results;
  if (!projects.some(p => p.id === project))
    project = (projects.find(p => p.campaign_id === campaign) || projects[0])?.id || "";
  $("#project").innerHTML = projects
                                .map(
                                    p => "<option value=\"" + p.id + "\">" + esc(p.title) + " · " +
                                        esc(p.id.slice(0, 8)) + "</option>")
                                .join("") ||
      "<option>Sin producciones</option>";
  $("#project").value = project;
  const current = project ? await api(prod()) : null;
  if (seq !== generation)
    return;
  doc = current;
  const q = new URLSearchParams({brand});
  if (project)
    q.set("production", project);
  if (campaign)
    q.set("campaign", campaign);
  history.replaceState(null, "", "/studio?" + q.toString() + location.hash);
  draw();
  connect();
  valid=true;
  loaded=true;
  } catch(error) {
    if(seq===generation) {
      doc=null;
      $("#workspace").innerHTML=panel("Carga pendiente","<p>"+esc(error.message)+"</p>"+btn("reload","Reintentar carga"));
    }
    throw error;
  } finally {
    if(seq===generation) setBusy(false,valid);
  }
}
function setBusy(busy,valid=true) {
  $("#workspace").inert=busy;
  $("#production").setAttribute("aria-busy",String(busy));
  $("#new-production").disabled=busy||!valid;
  $("#project").disabled=busy||!valid;
}
function story() {
  const busy = ["queued", "rendering"].includes(doc.state);
  const cards =
      doc.plan.shots
          .map((s, i) => {
            const selected = doc.selected[i], tag = "data-index=\"" + i + "\"";
            const comparisons =
                doc.candidates[i]
                    .map(
                        c => "<div>" + video(c.sha256, "preview") + "<p class=\"meta\">Candidato " +
                            c.candidate + " · " + c.sha256.slice(0, 8) + "</p>" +
                            (!busy && c.selectable && selected !== c.sha256 ?
                                 btn("select", "Usar candidato", tag + " data-hash=\"" + c.sha256 + "\"") :
                                 "") +
                            "</div>")
                    .join("");
            return "<article class=\"shot\"><span class=\"micro\">Plano " + s.order + " · " + s.duration +
                " s</span><h3>" + esc(s.caption) + "</h3>" +
                "<p>" + esc(s.camera) + "</p><p class=\"meta\">" + esc(s.prompt) + "</p>" +
                (selected ? video(selected, "preview") : "") + "<div class=\"actions\">" +
                (busy || (doc.home && !doc.home.reference_ready) ? "" : btn("edit-shot", "Editar plano", tag)) +
                (!busy && selected && doc.attempts[i] < 2 ? btn("regenerate", "Regenerar", tag) : "") +
                "</div>" +
                (comparisons ? "<details><summary>Candidatos (" + doc.candidates[i].length +
                         ")</summary><div class=\"pair\">" + comparisons + "</div></details>" :
                               "") +
                "</article>";
          })
          .join("");
  return panel(
             doc.provider === "home-local-v1" ? (doc.plan.simulated ? "Guion preparatorio MOCK · pendiente de Ollama" : "Guion HOME · Ollama") : "Guion MOCK",
             "<p>" + esc(doc.plan.idea) + "</p><p><strong>" + esc(doc.plan.script.hook) + "</strong></p><p>" +
                 esc(doc.plan.script.cta) + "</p>" + (busy ? "" : btn("rewrite", "Versionar idea")) +
                 "<p class=\"meta\">" + esc(doc.preset.name) + " · " + esc(doc.character.name) + " v" +
                 doc.character.version + "</p>" + (doc.home?.reference_ready ?
                 "<img class=\"character-ref\" alt=\"Referencia real de la producción\" src=\"" + url(doc.character.reference.sha256) + "\">" : "")) +
      "<div class=\"shots\">" + cards + "</div><details><summary>Historial del storyboard (" +
      doc.plan_history.length + ")</summary>" +
      doc.plan_history
          .map(
              (p, i) =>
                  "<p>Versión " + (i + 1) + " · " + p.shots.map(s => esc(s.caption)).join(" / ") + "</p>")
          .join("") +
      "</details>";
}
const downloads = {
  video: ["Reel", "mp4"],
  cover: ["Portada", "png"],
  subtitles: ["Subtítulos", "srt"],
  timeline: ["Timeline", "json"],
  copy: ["Copy", "txt"],
  manifest: ["Manifest", "json"]
};
function timeline() {
  const seq = doc.sequence || [1, 2, 3, 4, 5], busy = ["queued", "rendering"].includes(doc.state);
  return panel(
      "Timeline",
      seq.map(
             (n, i) => "<div class=\"row\"><div>" + esc(doc.plan.shots[n - 1].caption) + " · " +
                 doc.plan.shots[n - 1].duration + " s</div><div class=\"actions\">" +
                 (!busy && i > 0 ? btn("up", "Adelantar", "data-index=\"" + i + "\"") : "") +
                 (!busy && i < 4 ? btn("down", "Retrasar", "data-index=\"" + i + "\"") : "") + "</div></div>")
          .join(""));
}
function edit() {
  if (!doc.output.assets)
    return timeline() +
        panel("Montaje", "<p>El montaje estará disponible cuando terminen los cinco planos y el QC.</p>");
  const a = doc.output.assets, q = doc.output.qc;
  return timeline() +
      panel(doc.provider === "home-local-v1" ? "Reel HOME · IA local" : "Reel MOCK",
            video(a.video.sha256) + "<p>" + q.width + " × " + q.height + " · 24 fps · " + q.duration +
                " s · H.264 / AAC</p>" +
                "<p class=\"meta\">QC · pico " + q.peak_db + " dB · intervalos negros " + q.black_intervals +
                " · subtítulos incluidos</p><div class=\"actions\">" +
                Object.entries(downloads)
                    .map(
                        ([k, [n, ext]]) => "<a class=\"button\" download=\"" + (doc.provider === "home-local-v1" ? "HOME-" : "MOCK-") + k + "." + ext +
                            "\" href=\"" + url(a[k].sha256) + "\">" + n + "</a>")
                    .join("") +
                "</div>" +
                "<p class=\"meta\">SHA-256 · " + a.video.sha256 + "</p>") +
      (doc.exports.length ? panel(
                                "Montajes anteriores",
                                doc.exports
                                    .map(
                                        (x, i) => "<details><summary>Montaje " + (i + 1) + "</summary>" +
                                            video(x.assets.video.sha256) + "</details>")
                                    .join("")) :
                            "");
}
function review() {
  return panel(
      "Revisión humana",
      (doc.output.assets ? video(doc.output.assets.video.sha256) + btn("review", "Registrar revisión") :
                           "<p>Complete el montaje para revisarlo.</p>") +
          doc.reviews
              .map(
                  r => "<p>" + esc(r.reviewer) + " · " + esc(r.verdict) + " · " + esc(r.notes) +
                      "</p><p class=\"meta\">" + r.artifact_hash + "</p>")
              .join(""));
}
function calendar() {
  const approved = doc?.output.assets &&
      doc.active_review?.artifact_hash === doc.output.assets.video.sha256 &&
      doc.active_review?.verdict === "approved";
  const rows = publications
                   .map(
                       p => "<article class=\"row\"><div><h3>" + esc(names[p.status]) + "</h3><p>" +
                           esc(p.copy) + "</p><span class=\"meta\">" + date(p.scheduled_at) +
                           " · Madrid</span></div><div class=\"actions\">" +
                           (p.status === "scheduled" ?
                                btn("simulate", "Ejecutar dry-run", "data-id=\"" + p.id + "\"") +
                                    btn("stop", "Cancelar cita", "data-id=\"" + p.id + "\"") :
                                "") +
                           "</div></article>")
                   .join("");
  return panel(
             "Política de la marca",
             "<p>" + (policy.paused ? "En pausa" : "Activo") + " · " + policy.daily_limit +
                 " simulaciones al día · " + policy.start_hour + "–" + policy.end_hour +
                 " h (Madrid) · QC humano ≥ " + policy.min_score + "/5</p>" +
                 btn("policy", "Editar política")) +
      panel("Calendario dry-run",
            (approved ? btn("schedule", "Programar simulación") :
                        "<p>La programación requiere revisión aprobada del montaje actual.</p>") +
                rows) +
      panel("Analítica local",
            "<p>Simulaciones completadas: " + (metrics.counts.dry_run || 0) + "</p><p class=\"meta\">" +
                esc(metrics.fixture.label) + " · " + metrics.fixture.impressions + " impresiones · " +
                metrics.fixture.plays + " reproducciones</p>");
}
function library() {
  return panel(
             "Personajes",
             "<p>Las vistas de biblioteca son referencias procedurales MOCK. HOME genera una referencia SDXL a partir de la ficha del personaje y la conserva para sus cinco planos.</p>" +
             btn("character", "Crear versión de personaje") +
                 characters
                     .map(
                         c => "<article class=\"row\"><div><h3>" + esc(c.name) + " · v" + c.version +
                             "</h3><p>" + esc(c.description) + "</p><div class=\"pair\">" +
                             Object.entries({front: c.reference, ...c.views})
                                 .map(
                                     ([pose, a]) => "<img class=\"character-ref\" alt=\"" + esc(pose) +
                                         "\" src=\"/api/v1" + base() + "/characters/" + c.id + "/assets/" +
                                         a.sha256 + "\">")
                                 .join("") +
                             "</div><span class=\"meta\">" + esc(c.color) + " · referencia " +
                             c.reference.sha256.slice(0, 12) + "</span></div></article>")
                     .join("")) +
      (doc ? panel(
                 "Referencia de la producción",
                 "<img class=\"character-ref\" alt=\"Referencia del personaje\" src=\"" +
                     url(doc.character.reference.sha256) + "\">") :
             "") +
      panel("Presets",
            registry.presets
                .map(
                    p => "<p><b>" + esc(p.name) + "</b> · v" + p.version + " · " + esc(p.continuity) + "</p>")
                .join("")) +
      panel("Modelos y licencias",
            registry.providers
                    .map(p => "<p>" + esc(p.name) + " · " + esc(p.active ? p.license : p.reason) + "</p>")
                    .join("") +
                "<p>HOME usa los pesos verificados del equipo; los candidatos registrados aquí no se activan automáticamente.</p>" +
                (doc?.home?.models || []).map(m => "<p>"+esc(m.id)+" · "+esc(m.license_id)+
                  (m.license_asset ? " · <a href=\""+url(m.license_asset.sha256)+"\" download=\"LICENSE.txt\">Descargar licencia</a>" : "")+"</p>").join("") + btn("model", "Registrar candidato") +
                registry.models
                    .map(
                        m => "<p>" + esc(m.name) + " · " + esc(m.version) + " · " + esc(m.license_id) +
                            " · pendiente de validación local</p>")
                    .join(""));
}
function draw() {
  const home = doc?.provider === "home-local-v1";
  $(".environment").textContent = home ? "HOME / IA LOCAL" : "WORK / MOCK";
  for (const link of document.querySelectorAll("nav a")) {
    if (link.hash === "#" + tab())
      link.setAttribute("aria-current", "page");
    else
      link.removeAttribute("aria-current");
  }
  const section = tab();
  let body = doc ? "<div class=\"panel\"><div class=\"panel-head\"><h2>" + esc(doc.title) +
          "</h2><span class=\"tag\">" + esc(names[doc.state]) + "</span></div>" +
          "<p class=\"meta\">" + (home ? "HOME · " + esc(doc.home?.stage || "pending") + " · " : "MOCK · ") + doc.selected.filter(Boolean).length +
          "/5 planos guardados</p><div class=\"actions\">" +
          (["queued", "rendering"].includes(doc.state) ? btn("cancel", "Cancelar render") :
               !doc.output.assets                      ? btn("render", ["failed","cancelled"].includes(doc.state) ? "Reintentar / reanudar" : "Renderizar reel") :
                                                         "") +
          "</div>" + (doc.error ? "<p role=\"alert\">" + esc(doc.error) + "</p>" : "") + "</div>" :
                   "";
  if (section === "library")
    body += library();
  else if (section === "calendar")
    body += calendar();
  else if (!doc)
    body += panel("Sin producción", "<p>Elige una campaña al crear la primera producción.</p>");
  else
    body += section === "story" ? story() : section === "edit" ? edit() : review();
  if (doc)
    body += (home ? "<details><summary>Etapas HOME y recuperación</summary>" + doc.home.operations.map(o =>
      "<p class=\"meta\">" + esc(o.kind) + (o.index != null ? " · plano " + (o.index + 1) : "") + " · " + esc(o.state) +
      " · intento " + (o.attempt || 1) + " · ID " + esc(o.id) + (o.elapsed_seconds ? " · " + o.elapsed_seconds + " s" : "") + "</p>").join("") + "</details>" : "");
  if (doc)
    body += "<details><summary>Actividad (" + doc.activity.length + ")</summary>" +
        (doc.plan.trace || [])
            .map(
                t => "<p class=\"meta\">" + esc(t.role) + " · " + esc(t.prompt_version) + " · pasos " +
                    t.steps + "</p>")
            .join("") +
        doc.activity.map(e => "<p class=\"meta\">" + date(e.recorded_at) + " · " + esc(e.message) + "</p>")
            .join("") +
        "</details>";
  $("#workspace").innerHTML = body;
}
$("#new-brand").onclick = () => dialog("Crear marca", field("Nombre", input("name")), async b => {
  brand = (await api("/brands", "POST", b)).id;
  project = "";
  campaign = "";
});
$("#new-production").onclick = () => {
  if (!campaigns.length) {
    return dialog("Primera campaña de la marca", field("Nombre", input("name")) +
      field("Objetivo", area("objective")), async values => {
        campaign = (await api(base() + "/campaigns", "POST", values)).id;
      });
  }
  dialog(
      "Nueva producción",
      field("Proveedor", "<select name=\"provider\"><option value=\"mock-v1\">MOCK · CPU de prueba</option>" +
        (registry.providers.some(p => p.name === "home-local-v1" && p.active) ? "<option selected value=\"home-local-v1\">HOME · Ollama + SDXL + Wan</option>" : "") + "</select>") +
      field("Campaña", "<select name=\"campaign_id\">" + options(campaigns, "id", "name") + "</select>") +
          field("Idea", area("idea")) +
          field(
              "Preset", "<select name=\"preset\">" + options(registry.presets, "id", "name") + "</select>") +
          field(
              "Personaje",
              "<select name=\"character_id\"><option value=\"\">Lumen · predeterminado</option>" +
                  characters
                      .map(
                          c => "<option value=\"" + c.id + "\">" + esc(c.name) + " · v" + c.version +
                              "</option>")
                      .join("") +
                  "</select>"),
      async b => {
        if (!b.character_id)
          delete b.character_id;
        project = (await api(base() + "/productions", "POST", b)).id;
        location.hash = "story";
      });
  const select = $("#inputs [name=campaign_id]");
  if (campaigns.some(c => c.id === campaign))
    select.value = campaign;
  select.onchange = () => {
    $("#inputs textarea").value = campaigns.find(c => c.id === select.value).objective;
  };
  select.onchange();
};
$("#brand").onchange = () => {
  brand = $("#brand").value;
  project = "";
  campaign = "";
  disconnect();
  load().catch(e => say(e.message));
};
$("#project").onchange = () => {
  project = $("#project").value;
  disconnect();
  load().catch(e => say(e.message));
};
window.onhashchange = () => {
  if (loaded)
    draw();
};
$("#workspace").onclick = async e => {
  const b = e.target.closest("[data-do]");
  if (!b)
    return;
  const action = b.dataset.do, i = Number(b.dataset.index), shot = doc?.plan.shots[i];
  const post = (op, data) => api(prod() + "/" + op, "POST", data);
  if(action==="reload") return load().catch(e=>say(e.message));
  if (action === "policy")
    return dialog(
        "Política de la marca",
        [
          ["daily_limit", "Máximo diario", 1, 20], ["start_hour", "Hora de inicio", 0, 23],
          ["end_hour", "Hora de fin", 1, 24], ["min_score", "Umbral de revisión", 1, 5]
        ]
                .map(
                    ([k, n, min, max]) => field(
                        n,
                        "<input required type=\"number\" name=\"" + k + "\" min=\"" + min + "\" max=\"" +
                            max + "\" value=\"" + policy[k] + "\">"))
                .join("") +
            field(
                "Estado",
                "<select name=\"paused\"><option value=\"false\">Activo</option><option value=\"true\" " +
                    (policy.paused ? "selected" : "") + ">En pausa</option></select>"),
        v => api(base() + "/policy", "POST", {
          daily_limit: +v.daily_limit,
          start_hour: +v.start_hour,
          end_hour: +v.end_hour,
          min_score: +v.min_score,
          paused: v.paused === "true"
        }));
  if (action === "model")
    return dialog(
        "Registrar modelo candidato",
        field("Nombre", input("name")) + field("Versión", input("version")) +
            field("Fuente HTTPS", input("source_url", "", 500)) +
            field("SHA-256 de los pesos", input("sha256", "", 64)) +
            field("Licencia declarada", input("license_id")) + field("Restricciones", area("restrictions")) +
            field("Registrado por", input("checked_by")),
        v => api(base() + "/models", "POST", v));
  if (action === "rewrite")
    return dialog(
        "Versionar idea",
        field("Idea", area("idea", doc.plan.idea)) +
            field(
                "Cambiar preset",
                "<select name=\"preset\"><option value=\"\">Mantener preset</option>" +
                    options(registry.presets, "id", "name") + "</select>") +
            field(
                "Cambiar personaje",
                "<select name=\"character_id\"><option value=\"\">Mantener versión</option>" +
                    characters
                        .map(
                            c => "<option value=\"" + c.id + "\">" + esc(c.name) + " · v" + c.version +
                                "</option>")
                        .join("") +
                    "</select>"),
        v => post("rewrite", {
          idea: v.idea,
          preset: v.preset || null,
          character_id: v.character_id || null,
          revision: doc.revision
        }));
  if (action === "character")
    return dialog(
        "Versión de personaje",
        field("Nombre", input("name")) + field("Descripción", area("description")) +
            field(
                "Silueta",
                "<select name=\"shape\"><option value=\"pixel\">Píxel</option><option value=\"cursor\">Cursor</option><option value=\"orb\">Esfera</option></select>") +
            field("Color", "<input type=\"color\" name=\"color\" value=\"#ffe679\">"),
        v => api(base() + "/characters", "POST", v));
  if (action === "edit-shot")
    return dialog(
        "Editar plano " + shot.order,
        field("Subtítulo", input("caption", shot.caption)) +
            field("Descripción visual", area("prompt", shot.prompt)) +
            field(
                "Duración (s)",
                "<input type=\"number\" required min=\"3\" max=\"" + (doc.home ? "3" : "5") + "\" name=\"duration\" value=\"" +
                    shot.duration + "\">"),
        v => post("edit", {...v, duration: Number(v.duration), order: i + 1, revision: doc.revision}));
  if (action === "review")
    return dialog(
        "Revisión del montaje",
        field("Revisor", input("reviewer")) +
            field(
                "Decisión",
                "<select name=\"verdict\"><option value=\"rejected\">Solicitar cambios</option><option value=\"approved\">Aprobar dry-run</option></select>") +
            ["continuity", "movement", "narrative"]
                .map(
                    (k, i) => field(
                        ["Continuidad", "Movimiento", "Narrativa"][i],
                        "<input required type=\"number\" name=\"" + k + "\" min=\"1\" max=\"5\">"))
                .join("") +
            field("Observaciones", area("notes")),
        v => post("review", {
          ...v,
          continuity: +v.continuity,
          movement: +v.movement,
          narrative: +v.narrative,
          artifact_hash: doc.output.assets.video.sha256
        }));
  if (action === "schedule")
    return dialog(
        "Programar dry-run",
        field("Fecha y hora local del navegador", "<input required type=\"datetime-local\" name=\"date\">") +
            field("Copy", area("copy", doc.output.copy)),
        v => post("schedule", {
          scheduled_at: new Date(v.date).toISOString(),
          copy: v.copy,
          artifact_hash: doc.output.assets.video.sha256
        }));
  b.disabled = true;
  try {
    if (["up", "down"].includes(action)) {
      const order = [...(doc.sequence || [1, 2, 3, 4, 5])], j = action === "up" ? i - 1 : i + 1;
      [order[i], order[j]] = [order[j], order[i]];
      await post("sequence", {orders: order, revision: doc.revision});
    } else if (["stop", "simulate"].includes(action))
      await api(base() + "/publications/" + b.dataset.id + "/" + action, "POST");
    else
      await post(
          action,
          action === "select"         ? {order: i + 1, sha256: b.dataset.hash} :
              action === "regenerate" ? {order: i + 1} :
                                        undefined);
    await load();
    say("Operación registrada.");
  } catch (err) {
    say(err.message);
    b.disabled = false;
  }
};
load().catch(e => say(e.message));
