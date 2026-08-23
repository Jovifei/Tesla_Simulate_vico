(() => {
  "use strict";
  const data = window.S12_STAGE_U_REVIEW_DATA;
  const roles = ["reference", "parent", "candidate"];
  const metricNames = {matlab:"MATLAB", mosqito:"MoSQITo", audio_feature_extractor:"audioFeatureExtractor"};
  const timbralNames = {hardness:"硬度", depth:"深度", brightness:"明亮度", roughness:"粗糙度", warmth:"温暖度", sharpness:"锐度", booming:"轰鸣感", reverb:"混响感"};
  const state = {current:0, answers:{}, notes:{}, media_validation:{}};
  const select = document.getElementById("trial-select");
  const exportButton = document.getElementById("export");
  const gateStatus = document.querySelector('[data-testid="gate-status"]');

  function freshMediaState(trial) {
    if (!state.media_validation[trial.trial_id]) state.media_validation[trial.trial_id] = {};
    roles.forEach(role => {
      if (!state.media_validation[trial.trial_id][role]) state.media_validation[trial.trial_id][role] = {
        duration_s:0, duration:false, canplaythrough:false, sha256:"", sha_status:"PENDING"
      };
    });
  }
  function hex(buffer) { return Array.from(new Uint8Array(buffer), byte => byte.toString(16).padStart(2,"0")).join(""); }
  async function verifySha(trial, role, url) {
    const receipt = state.media_validation[trial.trial_id][role];
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("媒体读取失败");
      receipt.sha256 = hex(await crypto.subtle.digest("SHA-256", await response.arrayBuffer()));
      receipt.sha_status = receipt.sha256 === trial.media[role].sha256 ? "MATCH" : "MISMATCH";
    } catch (_) { receipt.sha_status = "READ_ERROR"; }
    updateGate();
  }
  function bindMedia(trial, role, audio, shaNode) {
    const receipt = state.media_validation[trial.trial_id][role];
    audio.src = trial.media[role].url;
    audio.onloadedmetadata = () => {
      receipt.duration_s = Number(audio.duration);
      receipt.duration = Number.isFinite(audio.duration) && audio.duration > 0 && Math.abs(audio.duration - trial.media[role].duration_s) < 0.08;
      updateGate();
    };
    audio.oncanplaythrough = () => { receipt.canplaythrough = true; updateGate(); };
    audio.onerror = () => { receipt.canplaythrough = false; updateGate(); };
    shaNode.textContent = `SHA-256 ${trial.media[role].sha256}`;
    verifySha(trial, role, trial.media[role].url);
  }
  function renderTimbral(trial) {
    const receipt = trial.timbral_descriptors;
    document.getElementById("timbral-status").textContent = `${receipt.status} · ${receipt.gate_label}`;
    const body = document.getElementById("timbral-body"); body.replaceChildren();
    Object.entries(receipt.descriptors).forEach(([name,value]) => {
      const row = document.createElement("tr");
      [`${timbralNames[name]}（${name}）`, value.before ?? "不可用", value.after ?? "不可用", value.status].forEach(text => { const cell=document.createElement("td"); cell.textContent=String(text); row.appendChild(cell); });
      body.appendChild(row);
    });
  }
  function renderResidual(trial, phase) {
    const receipt = trial.spectrogram_residuals[phase];
    document.getElementById(`spectrogram-${phase}-image`).src = receipt.url;
    const summary = receipt.summary;
    const comparisonName = receipt.comparison_role === "parent" ? "父版本" : "候选版本";
    document.getElementById(`spectrogram-${phase}-caption`).textContent = `平均绝对残差 ${summary.mean_absolute_db.toFixed(3)} dB · 均方根残差 ${summary.rms_db.toFixed(3)} dB · 95% 绝对残差 ${summary.p95_absolute_db.toFixed(3)} dB`;
    document.getElementById(`spectrogram-${phase}-trace`).textContent = `参考音轨 SHA-256 ${receipt.reference_raw_sha256} · ${comparisonName} SHA-256 ${receipt.comparison_raw_sha256} · SVG SHA-256 ${receipt.svg_sha256}`;
  }
  function renderTrial(index) {
    state.current = index;
    const trial = data.trials[index];
    freshMediaState(trial);
    document.getElementById("trial-meta").textContent = `${trial.vehicle_id} · ${trial.scenario} · ${trial.candidate_id}`;
    const statusLabels = document.getElementById("status-labels");
    statusLabels.replaceChildren();
    Object.values(trial.status_labels).forEach(label => {
      const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = label; statusLabels.appendChild(tag);
    });
    bindMedia(trial, "reference", document.querySelector('audio[data-role="reference"]'), document.querySelector('[data-sha="reference"]'));
    ["B","C"].forEach(slot => {
      const role = trial.randomized_mapping[slot];
      bindMedia(trial, role, document.querySelector(`audio[data-slot="${slot}"]`), document.querySelector(`[data-sha-slot="${slot}"]`));
    });
    const body = document.getElementById("metrics-body");
    body.replaceChildren();
    Object.entries(trial.professional_metrics).forEach(([name,value]) => {
      const row = document.createElement("tr");
      [metricNames[name] || name, value.before.toFixed(6), value.after.toFixed(6)].forEach(text => { const cell = document.createElement("td"); cell.textContent = text; row.appendChild(cell); });
      body.appendChild(row);
    });
    const parameters = document.getElementById("parameters");
    parameters.replaceChildren();
    Object.entries(trial.parameter_values).forEach(([name,value]) => { const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = `${name} = ${value}`; parameters.appendChild(tag); });
    document.getElementById("uncertainty").textContent = trial.parameter_uncertainty.display;
    renderTimbral(trial);
    renderResidual(trial, "before");
    renderResidual(trial, "after");
    document.querySelectorAll('input[name="answer"]').forEach(input => { input.checked = state.answers[trial.trial_id] === input.value; });
    document.getElementById("notes").value = state.notes[trial.trial_id] || "";
    updateGate();
  }
  function mediaReady(trial) {
    freshMediaState(trial);
    return roles.every(role => {
      const gate = state.media_validation[trial.trial_id][role];
      return gate.duration && gate.canplaythrough && gate.sha_status === "MATCH";
    });
  }
  function trialReady(trial) {
    return mediaReady(trial) && trial.parent_candidate_distinct === true && trial.professional_binding.passes === true && ["B","C"].includes(state.answers[trial.trial_id]);
  }
  function updateGate() {
    const current = data.trials[state.current];
    const allReady = data.trials.every(trialReady);
    exportButton.disabled = !allReady;
    if (!mediaReady(current)) gateStatus.textContent = "媒体校验未通过：需要有效时长、可连续播放事件与 SHA-256 一致。";
    else if (!current.parent_candidate_distinct) gateStatus.textContent = "门禁失败：父版本与候选版本必须不同。";
    else if (!current.professional_binding.passes) gateStatus.textContent = "门禁失败：缺少专业指标绑定。";
    else if (!["B","C"].includes(state.answers[current.trial_id])) gateStatus.textContent = "媒体已通过；请选择盲听通道 B 或 C。";
    else if (!allReady) gateStatus.textContent = "当前片段已完成；仍有其他片段未通过或未作答。";
    else gateStatus.textContent = "全部门禁与人工答案已齐备，可以导出提交文件。";
  }
  function submission() {
    const mappings = {}, sha_bindings = {}, responses = [];
    data.trials.forEach(trial => {
      mappings[trial.trial_id] = trial.randomized_mapping;
      sha_bindings[trial.trial_id] = trial.sha_bindings;
      responses.push({trial_id:trial.trial_id, answer:state.answers[trial.trial_id], notes:state.notes[trial.trial_id] || ""});
    });
    return {schema_version:"s12-stage-u-listener-submission-v1", manifest_sha256:data.manifest_sha256, submitted_at_utc:new Date().toISOString(), mappings, sha_bindings, media_validation:state.media_validation, responses};
  }
  function exportSubmission() {
    updateGate();
    if (exportButton.disabled) return;
    const blob = new Blob([JSON.stringify(submission(), null, 2) + "\n"], {type:"application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob); link.download = `Jovi_Stage_U_人工提交_${new Date().toISOString().replace(/[:.]/g,"-")}.json`; link.click(); URL.revokeObjectURL(link.href);
  }
  data.trials.forEach((trial,index) => { const option=document.createElement("option"); option.value=String(index); option.textContent=`${index+1}. ${trial.vehicle_id} / ${trial.scenario}`; select.appendChild(option); freshMediaState(trial); });
  select.addEventListener("change", () => renderTrial(Number(select.value)));
  document.querySelectorAll('input[name="answer"]').forEach(input => input.addEventListener("change", () => { state.answers[data.trials[state.current].trial_id]=input.value; updateGate(); }));
  document.getElementById("notes").addEventListener("input", event => { state.notes[data.trials[state.current].trial_id]=event.target.value; });
  exportButton.addEventListener("click", exportSubmission);
  renderTrial(0);
})();
