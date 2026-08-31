(function () {
  "use strict";
  const DATA = window.S12_RX7_TOPIC_R2_DATA || {};
  const pairs = DATA.pairs || [];
  const state = { selected: 0 };
  const esc = (value) => String(value == null ? "—" : value).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
  const fileUrl = (value) => { const path = String(value || "").replace(/\\/g, "/"); return path.match(/^file:/) ? path : "file:///" + path.replace(/^\/+/, ""); };
  const fmt = (value, digits = 3) => typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
  const metricNames = ["loudness_sone", "sharpness_acum", "roughness_asper", "fluctuation_vacil", "tone_to_noise_ratio_db", "prominence_ratio_db"];
  const ORDER_STATUS = "ORDER_COMPARISON_NOT_QUALIFIED";
  const scenarioNames = { idle: "怠速", steady_low: "低转稳定", steady_mid: "中转稳定", full_pull: "全负荷拉转", full_pull_interior: "车内全负荷拉转" };
  const renderMetricTable = (pair, domain, label) => {
    const value = pair[domain] || {};
    const reference = value.reference && value.reference.metrics ? value.reference.metrics : {};
    const candidate = value.candidate && value.candidate.metrics ? value.candidate.metrics : {};
    const delta = value.delta || {};
    return `<div class="chart"><h3>${esc(label)}</h3><table class="metric-table"><thead><tr><th>指标</th><th>参考</th><th>候选</th><th>差值</th></tr></thead><tbody>${metricNames.map((name) => `<tr><td>${esc(name)}</td><td>${fmt(reference[name])}</td><td>${fmt(candidate[name])}</td><td>${fmt(delta[name])}</td></tr>`).join("")}</tbody></table></div>`;
  };
  const renderPlayer = (pair, side, label) => {
    const meta = pair.window && pair.window[side] ? pair.window[side] : {};
    const audio = document.createElement("audio");
    audio.controls = true; audio.preload = "metadata"; audio.src = fileUrl(meta.path); audio.setAttribute("aria-label", label);
    const status = document.createElement("div"); status.className = "load-status"; status.textContent = "等待 canplaythrough…";
    const update = (ok, message) => { status.className = "load-status " + (ok ? "pass" : "fail"); status.textContent = ok ? `可播放 · ${fmt(audio.duration, 3)} s · SHA ${String(meta.sha256 || "—").slice(0, 12)}…` : message; };
    audio.addEventListener("canplaythrough", () => update(Number(audio.duration) > 0, Number(audio.duration) > 0 ? "SHA 已绑定" : "时长为 0，禁止试听"));
    audio.addEventListener("loadedmetadata", () => { if (Number(audio.duration) <= 0) update(false, "时长为 0，禁止试听"); });
    audio.addEventListener("error", () => update(false, "音频加载失败；请检查外部 Download 路径"));
    const box = document.createElement("div"); box.className = "player " + side; box.innerHTML = `<h3>${esc(label)}</h3>`; box.append(audio, status); return box;
  };
  function render() {
    const pair = pairs[state.selected]; if (!pair) return;
    document.querySelector("#pair-nav").innerHTML = pairs.map((item, index) => `<button class="${index === state.selected ? "active" : ""}" data-index="${index}">${esc(scenarioNames[item.scenario] || item.scenario)} · ${esc(item.window.profile)}</button>`).join("");
    document.querySelectorAll("#pair-nav button").forEach((button) => button.addEventListener("click", () => { state.selected = Number(button.dataset.index); render(); }));
    const proxy = pair.legacy_proxy || {};
    document.querySelector("#app").innerHTML = `<div class="pair-title"><div><div class="eyebrow">RX-7 FD / R2 TOPIC REVIEW</div><h2>${esc(scenarioNames[pair.scenario] || pair.scenario)} · ${esc(pair.window.profile)}</h2></div><span class="tag">R2 · ${esc((pair.order && pair.order.status) || ORDER_STATUS)}</span></div><div class="card"><div class="meta-grid"><div class="meta"><small>主题提示</small><strong>${esc((pair.focus_topics || []).join(" / "))}</strong></div><div class="meta"><small>参考场景</small><strong>${esc(pair.scenario)}</strong></div><div class="meta"><small>原生窗口</small><strong>${fmt(pair.window.duration_s, 3)} s</strong></div><div class="meta"><small>许可</small><strong>CC BY-NC-SA 4.0 · 非商业</strong></div><div class="meta"><small>参数组</small><strong>${esc(pair.parameter_group)}</strong></div></div><div class="players"></div><p class="load-status">主题是听审提示，不是自动判定。当前 RX-7 参考没有真实换挡/回火同步片段；转速主题只能做相对听感记录，不能生成 Order 结论。</p></div><div class="section-label">专业指标（reference / candidate / delta）</div><div class="metric-grid">${renderMetricTable(pair, "matlab", "Professional MATLAB")}${renderMetricTable(pair, "mosqito", "Professional MoSQITo")}</div><div class="section-label">Legacy Proxy（仅相对诊断）</div><div class="chart"><table class="metric-table"><thead><tr><th>项目</th><th>参考</th><th>候选</th><th>差值</th></tr></thead><tbody><tr><td>频谱距离</td><td>—</td><td>—</td><td>${fmt(proxy.delta && proxy.delta.spectral_distance, 4)}</td></tr><tr><td>频谱质心 Hz</td><td>${fmt(proxy.reference && proxy.reference.spectrum && proxy.reference.spectrum.centroid_hz, 2)}</td><td>${fmt(proxy.candidate && proxy.candidate.spectrum && proxy.candidate.spectrum.centroid_hz, 2)}</td><td>${fmt(proxy.delta && proxy.delta.centroid_hz, 2)}</td></tr><tr><td>瞬态事件数（Proxy）</td><td>${fmt(proxy.reference && proxy.reference.transient && proxy.reference.transient.event_count_proxy, 0)}</td><td>${fmt(proxy.candidate && proxy.candidate.transient && proxy.candidate.transient.event_count_proxy, 0)}</td><td>${fmt(proxy.delta && proxy.delta.transient && proxy.delta.transient.event_count_proxy, 0)}</td></tr></tbody></table></div><div class="section-label">候选参数</div><div class="chart"><p>本页候选只改一个参数组：<code>${esc(DATA.candidate && DATA.candidate.parameter_group)}</code>。</p><pre>${esc(JSON.stringify(DATA.candidate && DATA.candidate.parameter_overrides, null, 2))}</pre><p class="load-status">固定候选增益：${fmt(DATA.candidate && DATA.candidate.fixed_candidate_gain_db, 3)} dB；未修改 source/PTR/Radiation；不是自动最优调参。</p></div>`;
    const players = document.querySelector(".players"); players.append(renderPlayer(pair, "reference", "参考声源"), renderPlayer(pair, "candidate", "调整后候选"));
  }
  window.S12Rx7TopicR2 = { render };
  render();
})();
