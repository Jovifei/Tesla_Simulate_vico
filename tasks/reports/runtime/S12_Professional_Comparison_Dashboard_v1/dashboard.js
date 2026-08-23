(function () {
  "use strict";
  const DATA = window.S12_LONG_WINDOW_DATA || window.S12_PROFESSIONAL_DATA || {};
  const metrics = DATA.pair_metrics || {};
  const diagnosis = DATA.diagnosis || {};
  const plan = DATA.plan || {};
  const results = DATA.results || {};
  const state = { selected: 0, feedback: {}, audioReady: {}, audioErrors: {} };
  const problemOptions = ["太闷", "太薄", "太刺", "机械感不足", "机械感过强", "低频无冲击", "固定电子哨声", "转速变化不自然", "换挡不自然", "回火不自然", "循环/合成器伪影", "当前片段不包含", "无法判断", "其它"];
  const topicOptions = ["怠速", "加速", "减速/收油", "换挡", "回火/爆音", "转速变化", "音色/机械感"];
  const sceneTopics = (scenario) => {
    const label = String(scenario || "").toLowerCase(); const topics = [];
    if (label.includes("idle") || label.includes("startup")) topics.push("怠速");
    if (label.includes("acceleration") || label.includes("launch") || label.includes("full_load") || label.includes("full_pull") || label.includes("track")) topics.push("加速");
    if (label.includes("lift") || label.includes("deceleration") || label.includes("coast") || label.includes("afterfire")) topics.push("减速/收油");
    if (label.includes("shift") || label.includes("downshift")) topics.push("换挡");
    if (label.includes("afterfire") || label.includes("backfire")) topics.push("回火/爆音");
    if (label.includes("rpm") || label.includes("rev") || label.includes("acceleration")) topics.push("转速变化");
    return topics.length ? topics : ["音色/机械感"];
  };
  const esc = (value) => String(value == null ? "—" : value).replace(/[&<>\"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  const fileUrl = (value) => { const p = String(value || "").replace(/\\/g, "/"); return p.match(/^file:/) ? p : "file:///" + p.replace(/^\/+/, ""); };
  const currentPair = () => (metrics.pairs || [])[state.selected];
  const fmt = (value, digits = 3) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
  const domainRows = (pair, domain, label) => {
    const d = pair[domain] || {};
    const ref = d.reference && d.reference.metrics ? d.reference.metrics : {};
    const cand = d.candidate && d.candidate.metrics ? d.candidate.metrics : {};
    const delta = d.delta || {};
    const keys = ["loudness_sone", "sharpness_acum", "roughness_asper", "fluctuation_vacil", "tone_to_noise_ratio_db", "prominence_ratio_db"];
    return `<h3>${label}</h3><table class="metric-table"><thead><tr><th>指标</th><th>参考</th><th>候选</th><th>差值</th></tr></thead><tbody>${keys.map((key) => `<tr><td>${esc(key)}</td><td>${fmt(ref[key])}</td><td>${fmt(cand[key])}</td><td>${fmt(delta[key])}</td></tr>`).join("")}</tbody></table>`;
  };
  const linePath = (values, width = 600, height = 130) => {
    if (!Array.isArray(values) || !values.length) return "";
    const min = Math.min.apply(null, values), max = Math.max.apply(null, values), span = max - min || 1;
    return values.map((v, i) => `${i ? "L" : "M"}${(i / Math.max(values.length - 1, 1)) * width},${height - ((v - min) / span) * (height - 10) - 5}`).join(" ");
  };
  const renderSpectrum = (pair) => {
    const s = (pair.legacy_proxy || {}).spectrum_overlay;
    if (!s) return `<div class="chart"><h3>频谱叠图</h3><p class="load-status">当前收据未提供频率曲线，仅显示下方 8 频带。</p></div>`;
    return `<div class="chart"><h3>频谱叠图（Legacy Proxy）</h3><svg class="spectrum" viewBox="0 0 600 130" preserveAspectRatio="none"><path class="ref" d="${linePath(s.reference_db)}"></path><path class="cand" d="${linePath(s.candidate_db)}"></path></svg><div class="legend"><span class="ref">参考</span><span>候选</span></div></div>`;
  };
  const renderBands = (pair) => {
    const bands = (pair.legacy_proxy || {}).bands || {};
    const values = Object.keys(bands).map((name) => [name, Number(bands[name].delta || 0)]);
    const max = Math.max(0.01, ...values.map(([, v]) => Math.abs(v)));
    return `<div class="chart"><h3>8 频带差值</h3><div class="bars">${values.map(([name, value]) => { const width = Math.min(50, Math.abs(value) / max * 50); const left = value >= 0 ? 50 : 50 - width; return `<div class="bar-row"><span>${esc(name.replace("_", "–"))}</span><span class="bar-track"><i class="bar-zero"></i><i class="bar-fill ${value < 0 ? "negative" : ""}" style="left:${left}%;width:${width}%"></i></span><span class="bar-value">${fmt(value, 3)}</span></div>`; }).join("")}</div></div>`;
  };
  const renderHeatmap = (pair) => {
    const s = pair.spectrogram_residual;
    if (!s || !Array.isArray(s.values)) return `<div class="chart"><h3>spectrogram residual</h3><p class="load-status">无 residual 收据。</p></div>`;
    const flat = s.values.flat(), max = Math.max(1, ...flat.map((v) => Math.abs(Number(v) || 0)));
    const cells = s.values.flat().map((value) => { const n = Math.max(-1, Math.min(1, Number(value || 0) / max)); const hue = n >= 0 ? 184 : 34; const light = 24 + Math.abs(n) * 35; return `<i style="background:hsl(${hue} 75% ${light}%)"></i>`; }).join("");
    return `<div class="chart"><h3>spectrogram residual（候选−参考，dB）</h3><div class="heatmap">${cells}</div><p class="load-status">颜色仅表达相对残差，不代表绝对声压。</p></div>`;
  };
  const makeAudio = (pair, side, label) => {
    const evidence = pair.integrity && pair.integrity[side] ? pair.integrity[side] : {};
    const key = `${pair.pair_id}:${side}`;
    const audio = document.createElement("audio"); audio.controls = true; audio.preload = "metadata"; audio.src = fileUrl(pair[side + "_path"]); audio.setAttribute("aria-label", label);
    const status = document.createElement("div"); status.className = "load-status"; status.textContent = "等待 canplaythrough…";
    const mark = (ok, message) => { state.audioReady[key] = ok; state.audioErrors[key] = ok ? null : message; status.className = "load-status " + (ok ? "pass" : "fail"); status.textContent = ok ? `可播放 · ${fmt(audio.duration, 3)} s · SHA ${String(evidence.sha_status || "—")}` : message; updateSubmit(); };
    audio.addEventListener("canplaythrough", () => mark(Number(audio.duration) > 0 && evidence.sha_status === "MATCH", Number(audio.duration) > 0 ? "SHA 门未通过，禁止提交" : "时长为 0，禁止提交"));
    audio.addEventListener("loadedmetadata", () => { if (Number(audio.duration) <= 0) mark(false, "时长为 0，禁止提交"); });
    audio.addEventListener("error", () => mark(false, "音频加载失败，禁止提交"));
    const box = document.createElement("div"); box.className = "player " + (side === "reference" ? "reference" : "candidate"); box.innerHTML = `<h3>${label}</h3>`; box.append(audio, status); return box;
  };
  const vehicleIds = () => Array.from(new Set((metrics.pairs || []).map((pair) => pair.vehicle_id)));
  const pairsForVehicle = (vehicleId) => (metrics.pairs || []).filter((pair) => pair.vehicle_id === vehicleId);
  const feedbackFor = (vehicleId) => state.feedback[vehicleId] || { software_agreement: "", identity: "", realism: "", problems: [], focus_topics: [], preference: "", notes: "", review_ready: false };
  const renderFeedback = (pair) => {
    const vehicleId = pair.vehicle_id; const f = feedbackFor(vehicleId);
    const problems = problemOptions.map((p) => `<button type="button" class="problem-chip ${f.problems.indexOf(p) >= 0 ? "selected" : ""}" data-problem="${esc(p)}">${esc(p)}</button>`).join("");
    const topics = topicOptions.map((topic) => `<button type="button" class="topic-chip ${f.focus_topics.indexOf(topic) >= 0 ? "selected" : ""}" data-topic="${esc(topic)}">${esc(topic)}</button>`).join("");
    const currentTopics = sceneTopics(pair.scenario).join(" / ");
    const completed = vehicleIds().filter((id) => feedbackComplete(id)).length;
    return `<div class="card feedback" data-feedback-scope="vehicle"><h2>${esc(vehicleId)} · 车型汇总反馈</h2><p class="load-status">当前车型只提交一份评分；先听当前窗口，再确认本车型听审完成。</p><p class="theme-hint"><strong>当前窗口主题：</strong>${esc(currentTopics)} <span>（由场景标签提示，最终以你的主题选择为准）</span></p><div class="feedback-grid"><label>软件诊断是否符合听感<select data-feedback="software_agreement"><option value="">请选择</option><option ${f.software_agreement === "符合" ? "selected" : ""}>符合</option><option ${f.software_agreement === "部分符合" ? "selected" : ""}>部分符合</option><option ${f.software_agreement === "不符合" ? "selected" : ""}>不符合</option><option ${f.software_agreement === "无法判断" ? "selected" : ""}>无法判断</option></select></label><label>整体车型身份（0–100）<input data-feedback="identity" type="number" min="0" max="100" step="1" value="${esc(f.identity)}"></label><label>整体真实感（0–100）<input data-feedback="realism" type="number" min="0" max="100" step="1" value="${esc(f.realism)}"></label><label>更偏好<select data-feedback="preference"><option value="">请选择</option><option ${f.preference === "参考" ? "selected" : ""}>参考</option><option ${f.preference === "候选" ? "selected" : ""}>候选</option><option ${f.preference === "无明显偏好" ? "selected" : ""}>无明显偏好</option></select></label></div><label class="topic-label">本车型听审主题（至少选择一项）<span class="topic-chips">${topics}</span></label><label class="problem-label">最明显问题（点击标签，可多选）<span class="problem-chips">${problems}</span></label><label>自由备注<textarea data-feedback="notes">${esc(f.notes)}</textarea></label><label class="review-check"><input data-feedback="review_ready" type="checkbox" ${f.review_ready ? "checked" : ""}> 我已听完本车型当前窗口对比，确认提交这份车型评分</label><div class="actions"><button class="primary" id="export-feedback" type="button">提交全部车型反馈</button><span id="submit-status" class="submit-status">已完成车型 ${completed}/${vehicleIds().length}；需要三辆车都确认后提交。</span></div></div>`;
  };
  function collectCurrentFeedback(pair) {
    const root = document.querySelector(".feedback"); if (!root) return;
    const value = (key) => root.querySelector(`[data-feedback='${key}']`)?.value || "";
    const problems = Array.from(root.querySelectorAll(".problem-chip.selected")).map((button) => button.dataset.problem);
    const score = (key) => { const raw = value(key); return raw === "" ? "" : Number(raw); };
    const focus_topics = Array.from(root.querySelectorAll(".topic-chip.selected")).map((button) => button.dataset.topic);
    state.feedback[pair.vehicle_id] = { software_agreement: value("software_agreement"), identity: score("identity"), realism: score("realism"), problems, focus_topics, preference: value("preference"), notes: value("notes"), review_ready: Boolean(root.querySelector("[data-feedback='review_ready']")?.checked) };
  }
  function feedbackComplete(vehicleId) { const f = feedbackFor(vehicleId); return Boolean(f.review_ready) && Array.isArray(f.focus_topics) && f.focus_topics.length > 0 && [f.software_agreement, f.identity, f.realism, f.preference].every(Boolean) && Number.isInteger(f.identity) && Number.isInteger(f.realism) && f.identity >= 0 && f.identity <= 100 && f.realism >= 0 && f.realism <= 100; }
  function vehicleAudioReady(vehicleId) { return pairsForVehicle(vehicleId).some((pair) => state.audioReady[`${pair.pair_id}:reference`] && state.audioReady[`${pair.pair_id}:candidate`]); }
  function allAudioReady() { return vehicleIds().every(vehicleAudioReady); }
  function allFeedbackComplete() { return vehicleIds().every(feedbackComplete); }
  function updateSubmit() { const button = document.getElementById("export-feedback"); const status = document.getElementById("submit-status"); if (!button) return; const audioOk = allAudioReady(), feedbackOk = allFeedbackComplete(); button.disabled = !(audioOk && feedbackOk); const completed = vehicleIds().filter((id) => feedbackComplete(id)).length; status.textContent = audioOk && feedbackOk ? "三辆车硬门通过，可提交全部反馈。" : `不能提交：已完成车型=${completed}/${vehicleIds().length}，音频门=${audioOk ? "通过" : "请至少听完每车型一个当前窗口"}。`; }
  function render() {
    const pair = currentPair(); if (!pair) return;
    document.getElementById("trial-nav").innerHTML = (metrics.pairs || []).map((item, index) => `<button class="${index === state.selected ? "active" : ""}" data-index="${index}">${esc(item.vehicle_id)} · ${esc(item.pair_id)}</button>`).join("");
    document.querySelectorAll("#trial-nav button").forEach((b) => b.addEventListener("click", () => { collectCurrentFeedback(pair); state.selected = Number(b.dataset.index); render(); }));
    const diag = (diagnosis.vehicles || []).find((v) => v.vehicle_id === pair.vehicle_id); const items = (diag && diag.items || []).map((item) => `<div class="diag-item">${esc(item.diagnosis_zh)}<small>依据：${esc(item.basis)} · 不确定性：${esc(item.uncertainty)}</small></div>`).join("") || `<div class="diag-item">当前没有该锚点的文字诊断。</div>`;
    const anchorPlan = (plan.anchors || []).find((a) => a.vehicle_id === pair.vehicle_id);
    const profile = pair.window_profile || (pair.window && pair.window.profile) || "5s";
    document.getElementById("app").innerHTML = `<div class="pair-title"><div><div class="eyebrow">EXACT TRIAL / SOFTWARE FIRST</div><h2>${esc(pair.vehicle_id)} · ${esc(pair.pair_id)}</h2></div><span class="tag">${esc(profile)} · ${esc(pair.reference_class)} · ${esc(pair.order.status)}</span></div><div class="card"><div class="meta-grid"><div class="meta"><small>场景</small><strong>${esc(pair.scenario)}</strong></div><div class="meta"><small>窗口</small><strong>${esc(profile)}</strong></div><div class="meta"><small>参考等级</small><strong>${esc(pair.reference_class)}</strong></div><div class="meta"><small>麦克风/AGC不确定性</small><strong>${esc(pair.microphone_uncertainty)}</strong></div><div class="meta"><small>SHA/file-ID</small><strong>${esc(pair.file_id)}</strong></div></div><div class="players"></div><div class="section-label">软件诊断</div><div class="diag">${items}</div><div class="section-label">频谱与残差</div><div class="chart-grid">${renderBands(pair)}${renderSpectrum(pair)}${renderHeatmap(pair)}</div><div class="section-label">专业指标（reference / candidate / delta）</div><div class="metric-grid"><div class="chart">${domainRows(pair, "matlab", "Professional MATLAB")}</div><div class="chart">${domainRows(pair, "mosqito", "Professional MoSQITo")}</div></div><div class="section-label">R2 有界诊断候选</div><div class="chart"><h3>${esc(anchorPlan?.parameter_group || "未定义")}</h3><p class="load-status">最多 ${esc(anchorPlan?.candidate_spec_count || 0)} 个规格；当前只生成规格，不渲染、不写声源、不声明 before/after。</p><div class="candidate-list">${(anchorPlan?.candidate_specs || []).slice(0, 8).map((c) => `<code>${esc(c.candidate_id)} · ${esc(JSON.stringify(c.parameter_values))}</code>`).join("")}<span>…其余规格见 r2_diagnostic_candidate_results.json</span></div></div></div>${renderFeedback(pair)}`;
    const players = document.querySelector(".players"); players.append(makeAudio(pair, "reference", "参考播放器"), makeAudio(pair, "candidate", "候选播放器"));
    document.querySelectorAll("[data-feedback]").forEach((el) => el.addEventListener("input", () => { collectCurrentFeedback(pair); updateSubmit(); }));
    document.querySelectorAll(".problem-chip").forEach((chip) => chip.addEventListener("click", () => { chip.classList.toggle("selected"); collectCurrentFeedback(pair); updateSubmit(); }));
    document.querySelectorAll(".topic-chip").forEach((chip) => chip.addEventListener("click", () => { chip.classList.toggle("selected"); collectCurrentFeedback(pair); updateSubmit(); }));
    document.getElementById("export-feedback").addEventListener("click", () => exportFeedback()); updateSubmit();
  }
  function exportFeedback() {
    const pair = currentPair(); collectCurrentFeedback(pair);
    if (!allAudioReady() || !allFeedbackComplete()) { updateSubmit(); return null; }
    const payload = { schema_version: "s12-professional-jovi-guided-feedback-v3", feedback_scope: "vehicle", package_manifest_sha256: metrics.manifest_sha256 || null, window_profiles_s: metrics.window_profiles_s || [5], evidence_level: "R3", status: "READY_FOR_REVIEW", automatic_tuning_eligible: false, profile_update: "FORBIDDEN", exported_at_utc: new Date().toISOString(), audio_submit_gate: { status: "PASS", required: ["canplaythrough", "duration>0", "reference_sha_match", "candidate_sha_match", "required_files"] }, rows: vehicleIds().map((vehicleId) => ({ vehicle_id: vehicleId, pair_ids: pairsForVehicle(vehicleId).map((item) => item.pair_id), file_ids: pairsForVehicle(vehicleId).map((item) => item.file_id), reference_sha256s: pairsForVehicle(vehicleId).map((item) => item.reference_sha256), candidate_sha256s: pairsForVehicle(vehicleId).map((item) => item.candidate_sha256), ...feedbackFor(vehicleId) })) };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "Jovi_Guided_Feedback.json"; link.click(); URL.revokeObjectURL(link.href); return payload;
  }
  window.S12Dashboard = { exportFeedback };
  render();
})();
