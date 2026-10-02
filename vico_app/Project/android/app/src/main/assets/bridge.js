(function(){
  document.documentElement.classList.add('vico-page-loading');
  // 默认 no-op; 各页内联脚本 (dashboard/calibration) 提供实际 __vicoUpdate 处理
  window.__vicoUpdate = window.__vicoUpdate || function(){};

  function nav(route){
    try { window.AndroidBridge.navigate(route); }
    catch(e){ console.log('vico nav fail', route, e); }
  }

  function syncNativeState(){
    try {
      var raw = window.AndroidBridge && window.AndroidBridge.getStateJson();
      if (!raw) return;
      var state = JSON.parse(raw);
      applyLanguage(state.language || 'zh');
      if (window.__vicoUpdate) window.__vicoUpdate(state);
    } catch(e) { console.log('vico state sync failed', e); }
  }

  var translations = {
    'VICO 电车声浪模拟器': 'VICO EV Sound Simulator',
    '实时状态': 'Live status',
    '当前配置': 'Current profile',
    '启用声浪': 'Enable sound',
    '停止声浪': 'Stop sound',
    '已选择': 'Selected',
    '选择': 'Select',
    '校准': 'Calibrate',
    '声浪配置': 'Sound profile',
    '柔和': 'Soft',
    '运动': 'Sport',
    '科幻': 'Sci-Fi',
    '演示模式': 'Demo mode',
    '停止': 'Stop',
    '起步': 'Launch',
    '巡航': 'Cruise',
    '减速': 'Decelerate',
    '极速': 'Max speed',
    '重置当前配置': 'Reset sound settings',
    '全部重置': 'Reset all',
    '导出 CSV': 'Export CSV',
    '仪表盘': 'Dashboard',
    '声音库': 'Sound library',
    '设置': 'Settings',
    '输出选择': 'Output',
    '速度单位': 'Speed unit',
    '主题': 'Theme',
    '遥测日志记录': 'Telemetry logging',
    '重置校准': 'Reset calibration',
    '主音量': 'Master volume',
    '加速度': 'Acceleration',
    '虚拟转速': 'Virtual RPM'
    ,'GPS 信号丢失，当前使用加速度传感器数据。': 'GPS signal lost. Using accelerometer data.'
    ,'良好': 'Good'
    ,'丢失': 'Lost'
  };

  function applyLanguage(language){
    var english = language === 'en';
    document.documentElement.lang = english ? 'en' : 'zh-CN';
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function(node){
      var parent = node.parentElement;
      if (!parent || /^(SCRIPT|STYLE)$/i.test(parent.tagName)) return;
      if (parent.dataset.vicoOriginalText === undefined) parent.dataset.vicoOriginalText = node.nodeValue;
      var original = parent.dataset.vicoOriginalText;
      var trimmed = original.trim();
      if (!english) { node.nodeValue = original; return; }
      if (translations[trimmed]) node.nodeValue = original.replace(trimmed, translations[trimmed]);
    });
  }

  function wire(){
    // 底部 3 标签导航: 仪表盘 / 声音库 / 设置
    document.querySelectorAll('span.material-symbols-outlined').forEach(function(s){
      var icon = (s.textContent || '').trim();
      var route = icon === 'dashboard' ? 'dashboard'
                : icon === 'library_music' ? 'library'
                : icon === 'settings' ? 'settings' : null;
      if (!route) return;
      var el = s.closest('div') || s.parentElement;
      // 用 data-vico-wired 去重 (独立于 haiku 预置的 data-vico-nav 标记, 否则预标记的 nav 不会被绑定)
      if (el && !el.getAttribute('data-vico-wired')) {
        el.setAttribute('data-vico-wired', '1');
        el.style.cursor = 'pointer';
        el.addEventListener('click', function(e){ e.preventDefault(); nav(route); });
      }
    });
  }

  // 应用持久化主题 (设置页 setTheme 写入 localStorage)
  try {
    if (localStorage.getItem('vico-theme') === 'dark') {
      document.documentElement.classList.add('dark');
    }
  } catch(e){}

  function revealPage(){
    document.documentElement.classList.remove('vico-page-loading');
    document.documentElement.classList.add('icons-ready', 'vico-page-ready');
  }

  // 图标字体就绪前隐藏图标名 (避免 dashboard/library_music 等英文文本闪现)
  try {
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(revealPage);
    }
  } catch(e){}
  // 兜底: 字体状态异常时仍避免空白页。
  setTimeout(revealPage, 700);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire);
  else wire();
  setTimeout(syncNativeState, 0);
  window.__vicoWireNav = wire;
  window.__vicoSyncState = syncNativeState;
  window.__vicoApplyLanguage = applyLanguage;
})();
